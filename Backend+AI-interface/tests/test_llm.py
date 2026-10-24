"""
OpenAI 兼容模型接入：客户端解析、供应商设置、两段式回复（建议 + 结构化计划）与回退。
所有网络调用都被替换为本地假响应，不会访问任何真实模型服务。
"""

import io
import json
import urllib.error
from datetime import timedelta

import pytest
from conftest import body

from app.ai import llm
from app.core import crypto, timeutil


class FakeResponse:
    def __init__(self, payload):
        self._data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def completion(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


@pytest.fixture
def fake_llm(monkeypatch):
    """按顺序返回预设响应；记录每次请求的 URL、Header 与请求体。"""
    calls, queue = [], []

    def urlopen(request, timeout=None):
        calls.append({"url": request.full_url, "headers": dict(request.header_items()),
                      "body": json.loads(request.data) if request.data else None})
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)
    return calls, queue


def http_error(code, message="bad"):
    return urllib.error.HTTPError("http://x", code, "err", {}, io.BytesIO(json.dumps({"error": {"message": message}}).encode()))


# ---------------------------------------------------------------- 客户端
def test_extract_json_variants():
    assert llm.extract_json('{"a": 1}') == {"a": 1}
    assert llm.extract_json('好的：\n```json\n{"a": {"b": "x}y"}}\n```\n祝学习顺利') == {"a": {"b": "x}y"}}
    assert llm.extract_json('<think>先想想 {"no": 1}</think>结果 {"ok": true} 结束') == {"ok": True}
    with pytest.raises(llm.LlmError):
        llm.extract_json("抱歉，我无法回答")


def test_url_building_and_validation():
    assert llm.chat_url("https://api.deepseek.com/v1/") == "https://api.deepseek.com/v1/chat/completions"
    assert llm.chat_url("https://x.com/v1/chat/completions") == "https://x.com/v1/chat/completions"
    assert llm.models_url("http://localhost:11434/v1") == "http://localhost:11434/v1/models"
    with pytest.raises(llm.LlmError):
        llm.validate_base_url("ftp://x.com")
    with pytest.raises(llm.LlmError):
        llm.validate_base_url("http://127.0.0.1:11434/v1", allow_private=False)
    assert llm.validate_base_url("http://127.0.0.1:11434/v1", allow_private=True)


def test_json_mode_fallback_and_errors(fake_llm):
    calls, queue = fake_llm
    config = llm.ModelConfig(base_url="https://m.example.com/v1", api_key="sk-test", model="m1")
    queue += [http_error(400, "response_format not supported"), completion('{"x": 1}')]
    assert llm.chat_json(config, [{"role": "user", "content": "hi"}]) == {"x": 1}
    assert "response_format" in calls[0]["body"] and "response_format" not in calls[1]["body"]
    assert calls[0]["headers"]["Authorization"] == "Bearer sk-test"

    queue.append(http_error(401))
    with pytest.raises(llm.LlmError, match="API Key"):
        llm.chat(config, [])
    queue.append(urllib.error.URLError("connection refused"))
    with pytest.raises(llm.LlmError, match="无法连接"):
        llm.chat(config, [])


def test_crypto_round_trip():
    token = crypto.encrypt("sk-secret-123456")
    assert token and "sk-secret" not in token
    assert crypto.decrypt(token) == "sk-secret-123456"
    assert crypto.decrypt("garbage") == ""


# ---------------------------------------------------------------- 设置接口
def test_provider_crud_never_leaks_key(client, register):
    alice, _ = register()
    bob, _ = register()
    data = body(client.post("/ai/providers", headers=alice, json={
        "name": "我的 Kimi", "base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k",
        "api_key": "sk-abcdefghijklmnop"}))
    item = data["providers"][0]
    assert item["key_masked"] == "sk-****mnop" and item["active"] is True
    assert data["active"] == str(item["id"]) and data["resolved"]["label"] == "我的 Kimi · moonshot-v1-8k"
    assert "sk-abcdefghijklmnop" not in json.dumps(data)
    assert len(data["presets"]) >= 6

    # 改名但不传 Key：保留原 Key
    updated = body(client.put(f"/ai/providers/{item['id']}", headers=alice, json={"name": "Kimi"}))
    assert updated["providers"][0]["key_masked"] == "sk-****mnop"

    # 别人看不到、改不了、也不能切换到这份配置
    assert body(client.get("/ai/settings", headers=bob))["providers"] == []
    body(client.put(f"/ai/providers/{item['id']}", headers=bob, json={"name": "x"}), 404)
    body(client.put("/ai/settings", headers=bob, json={"active": str(item["id"])}), 404)

    body(client.put("/ai/settings", headers=alice, json={"active": "rule"}))
    assert body(client.get("/ai/health", headers=alice))["provider"] == "rule"
    after = body(client.delete(f"/ai/providers/{item['id']}", headers=alice))
    assert after["providers"] == [] and after["active"] == "rule"


def test_provider_validation(client, auth):
    body(client.post("/ai/providers", headers=auth, json={"name": "x", "base_url": "ftp://bad.example", "model": "m"}), 422)
    body(client.put("/ai/settings", headers=auth, json={"active": "anything"}), 422)


def test_probe_endpoints(client, auth, fake_llm):
    _, queue = fake_llm
    queue.append(completion("OK"))
    data = body(client.post("/ai/providers/test", headers=auth, json={
        "base_url": "https://m.example.com/v1", "model": "m1", "api_key": "sk-x"}))
    assert data["reply"] == "OK" and data["latency_ms"] >= 0
    queue.append({"data": [{"id": "m2"}, {"id": "m1"}]})
    assert body(client.post("/ai/providers/models", headers=auth, json={"base_url": "https://m.example.com/v1"}))["models"] == ["m1", "m2"]
    queue.append(http_error(401))
    response = client.post("/ai/providers/test", headers=auth, json={"base_url": "https://m.example.com/v1", "model": "m1"})
    assert body(response, 400) is None and "API Key" in response.json()["message"]


# ---------------------------------------------------------------- 两段式回复
def _use_model(client, headers):
    body(client.post("/ai/providers", headers=headers, json={
        "name": "测试模型", "base_url": "https://m.example.com/v1", "model": "m1", "api_key": "sk-x"}))


def test_llm_reply_has_advice_and_validated_plan(client, auth, fake_llm):
    calls, queue = fake_llm
    _use_model(client, auth)
    day = (timeutil.today() + timedelta(days=2)).isoformat()
    queue.append(completion(json.dumps({
        "advice": "- 先做真题\n- 错题当天订正",
        "title": "高数冲刺",
        "tasks": [
            {"date": day, "start_time": "19:00", "duration_minutes": 45, "title": "高数：真题", "priority": 3},
            {"date": day, "start_time": "23:30", "duration_minutes": 45, "title": "熬夜不行"},
            {"date": "1999-01-01", "start_time": "19:00", "duration_minutes": 45, "title": "日期不对"},
        ],
        "courses": [
            {"course_name": "数据库选修", "day_of_week": 3, "start_period": 9, "end_period": 10, "weeks": [1, 2, 3]},
            {"course_name": "坏数据", "day_of_week": 9, "start_period": 1, "end_period": 2},
        ],
    }, ensure_ascii=False)))
    draft = body(client.post("/ai/plan", headers=auth, json={
        "message": "复习高数，我周三晚上还有数据库选修", "start_date": day, "days": 1,
        "history": [{"role": "user", "content": "上次的计划太满了"}]}))

    assert draft["provider"] == "llm" and draft["model"] == "测试模型 · m1"
    assert draft["advice"].startswith("- 先做真题") and draft["title"] == "高数冲刺"
    assert [t["title"] for t in draft["tasks"]] == ["高数：真题"]
    assert [c["course_name"] for c in draft["courses"]] == ["数据库选修"]
    assert draft["courses"][0]["week_text"] == "1-3周" and draft["courses"][0]["start_time"] == "19:00"
    assert len(draft["warnings"]) == 2

    sent = calls[-1]["body"]["messages"]
    assert sent[0]["role"] == "system" and "advice" in sent[0]["content"]
    assert sent[1] == {"role": "user", "content": "上次的计划太满了"}
    assert "free_slots" in sent[-1]["content"]

    saved = body(client.post("/ai/plan/commit", headers=auth, json=draft))
    assert saved["plan"]["task_total"] == 1 and [c["course_name"] for c in saved["courses_saved"]] == ["数据库选修"]
    table = body(client.get("/timetable", headers=auth))
    assert any(c["course_name"] == "数据库选修" for c in table["courses"])

    # 再导入一次：课程与刚才完全冲突，被跳过而不是整体失败
    again = body(client.post("/ai/plan/commit", headers=auth, json={**draft, "import_tasks": False}))
    assert again["plan"] is None and again["courses_saved"] == []
    assert "冲突" in again["courses_skipped"][0]["reason"]


def test_llm_failure_falls_back_to_rule_engine(client, auth, fake_llm):
    _, queue = fake_llm
    _use_model(client, auth)
    target = (timeutil.today() + timedelta(days=3)).isoformat()
    queue.append(http_error(503))
    draft = body(client.post("/ai/plan", headers=auth, json={"message": "复习英语", "start_date": target, "days": 1}))
    assert draft["provider"] == "rule" and draft["fallback_reason"] == "模型服务暂时不可用"
    assert draft["tasks"] and draft["advice"]

    queue.append(completion(json.dumps({"advice": "x", "tasks": [{"date": target, "start_time": "03:00",
                                                                   "duration_minutes": 30, "title": "凌晨"}]})))
    draft = body(client.post("/ai/plan", headers=auth, json={"message": "复习英语", "start_date": target, "days": 1}))
    assert draft["provider"] == "rule" and "空闲时段" in draft["fallback_reason"]


def test_rule_mode_never_calls_model(client, auth, fake_llm):
    calls, _ = fake_llm
    _use_model(client, auth)
    body(client.put("/ai/settings", headers=auth, json={"active": "rule"}))
    draft = body(client.post("/ai/plan", headers=auth, json={"message": "复习物理"}))
    assert draft["provider"] == "rule" and draft["courses"] == [] and draft["advice"]
    assert calls == []
