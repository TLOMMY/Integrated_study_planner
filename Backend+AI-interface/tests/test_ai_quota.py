"""
AI 用量限额——只限制服务器 DeepSeek Key；用户自己的 Key、管理员不限；
一次对话回合（多步工具调用）只算 1 次；token 计入；超额 429；管理后台可改上限并看统计。
模型调用全部由本地假服务应答，不访问外网。
"""

import json

import pytest
from conftest import body

from app.ai import llm
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import AppSetting
from app.services import ai_quota

ADMIN = "admin@example.com"


class FakeStream:
    def __init__(self, lines):
        self._lines = [line.encode("utf-8") for line in lines]

    def readline(self):
        return self._lines.pop(0) if self._lines else b""

    def close(self):
        pass


class Plain:
    def __init__(self, payload):
        self._data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def sse(*chunks):
    lines = []
    for chunk in chunks:
        lines += [f"data: {json.dumps(chunk, ensure_ascii=False)}\n", "\n"]
    return FakeStream(lines + ["data: [DONE]\n", "\n"])


def text_reply(text, usage=None):
    return sse({"choices": [{"index": 0, "delta": {"content": text}}]},
               {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})


def tool_reply(name, args):
    return sse({"choices": [{"index": 0, "delta": {"tool_calls": [
        {"index": 0, "id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
         "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}})


@pytest.fixture
def server_key(monkeypatch):
    """模拟服务器配置了 DeepSeek Key；所有请求由假服务应答。"""
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-server-test")
    calls, queue = [], []

    def urlopen(request, timeout=None):
        calls.append({"url": request.full_url, "body": json.loads(request.data) if request.data else None})
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)
    yield calls, queue


@pytest.fixture(autouse=True)
def _restore_limits():
    yield
    db = SessionLocal()
    try:
        db.query(AppSetting).filter(AppSetting.key.in_([ai_quota.KEY_CALLS, ai_quota.KEY_TOKENS])).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def set_limits(calls=None, tokens=None):
    db = SessionLocal()
    try:
        ai_quota.set_limits(db, calls, tokens)
        db.commit()
    finally:
        db.close()


def admin_headers(client):
    response = client.post("/auth/register", json={"email": ADMIN, "password": "secret123", "full_name": "管理员"})
    data = response.json()["data"] if response.status_code == 200 else \
        body(client.post("/auth/login", json={"identifier": ADMIN, "password": "secret123"}))
    return {"Authorization": f"Bearer {data['access_token']}"}


def new_conversation(client, headers):
    return body(client.post("/ai/conversations", headers=headers, json={}))["id"]


def chat(client, headers, cid, message="今天学什么"):
    return client.post(f"/ai/conversations/{cid}/chat", headers=headers, json={"message": message})


def quota(client, headers):
    return body(client.get("/ai/health", headers=headers))["quota"]


# ---------------------------------------------------------------- 次数与 token
def test_server_key_counts_calls_and_blocks_with_429(client, auth, server_key):
    _, queue = server_key
    set_limits(calls=2, tokens=0)
    cid = new_conversation(client, auth)
    state = quota(client, auth)
    assert state["limited"] and state["calls_left"] == 2 and state["calls_limit"] == 2 and state["tokens_limit"] is None

    queue += [text_reply("第一条回复"), text_reply("第二条回复")]
    assert chat(client, auth, cid).status_code == 200
    assert quota(client, auth)["calls_left"] == 1
    assert chat(client, auth, cid).status_code == 200
    state = quota(client, auth)
    assert state["calls_left"] == 0 and state["exceeded"] and state["tokens_used"] == 30

    before = len(body(client.get(f"/ai/conversations/{cid}/messages", headers=auth))["items"])
    blocked = chat(client, auth, cid)
    payload = blocked.json()
    assert blocked.status_code == 429 and payload["data"]["reason"] == "ai_quota"
    assert "明天" in payload["message"] and "自己的模型 Key" in payload["message"] and "本地规则引擎" in payload["message"]
    # 超额时不保存用户消息、不请求模型
    assert len(body(client.get(f"/ai/conversations/{cid}/messages", headers=auth))["items"]) == before
    assert not queue

    # 其他 AI 入口同样受限：规划草稿
    body(client.post("/ai/plan", headers=auth, json={"message": "明天复习高数 1 小时"}), 429)
    # 切到本地规则引擎不受限
    body(client.put("/ai/settings", headers=auth, json={"active": "rule"}))
    assert body(client.post("/ai/plan", headers=auth, json={"message": "明天复习高数 1 小时"}))["provider"] == "rule"


def test_multi_step_tool_turn_counts_once_and_records_tokens(client, auth, server_key):
    calls, queue = server_key
    set_limits(calls=5, tokens=0)
    cid = new_conversation(client, auth)
    queue += [tool_reply("get_context", {}), text_reply("看过了，今晚复习线代。")]
    assert chat(client, auth, cid).status_code == 200
    assert len(calls) == 2
    state = quota(client, auth)
    assert state["calls_used"] == 1 and state["tokens_used"] == 135


def test_token_limit_blocks_next_call(client, auth, server_key):
    _, queue = server_key
    set_limits(calls=0, tokens=100)
    cid = new_conversation(client, auth)
    queue.append(text_reply("一条很长的回复", usage={"prompt_tokens": 120, "completion_tokens": 30}))
    assert chat(client, auth, cid).status_code == 200
    state = quota(client, auth)
    assert state["tokens_used"] == 150 and state["tokens_left"] == 0 and state["exceeded"]
    blocked = chat(client, auth, cid)
    assert blocked.status_code == 429 and "100 tokens" in blocked.json()["message"]


def test_non_stream_entry_points_are_counted(client, auth, server_key):
    """规划草稿走非流式 chat_json：也计数，且读到返回的 usage。"""
    _, queue = server_key
    set_limits(calls=1, tokens=0)
    queue.append(Plain({"choices": [{"message": {"content": json.dumps({"advice": "先看例题", "tasks": []})}}],
                        "usage": {"prompt_tokens": 40, "completion_tokens": 2, "total_tokens": 42}}))
    body(client.post("/ai/plan", headers=auth, json={"message": "明天复习高数 1 小时"}))
    state = quota(client, auth)
    assert state["calls_used"] == 1 and state["tokens_used"] == 42 and state["calls_left"] == 0
    # 超额后在真正请求模型前被拦下（队列里没有响应，若发出请求会报错）
    body(client.post("/ai/plan", headers=auth, json={"message": "后天复习线代 1 小时"}), 429)


def test_own_key_and_admin_are_not_limited(client, auth, server_key):
    _, queue = server_key
    set_limits(calls=1, tokens=0)
    # 用户自己的 Key：不计数、不限
    body(client.post("/ai/providers", headers=auth, json={
        "name": "我的模型", "base_url": "https://m.example.com/v1", "model": "my-model", "api_key": "sk-mine"}))
    assert body(client.get("/ai/health", headers=auth))["quota"] is None
    cid = new_conversation(client, auth)
    queue += [text_reply("一"), text_reply("二")]
    assert chat(client, auth, cid).status_code == 200
    assert chat(client, auth, cid).status_code == 200

    # 管理员用服务器 Key 也不限
    headers = admin_headers(client)
    body(client.put("/ai/settings", headers=headers, json={"active": "auto"}))
    state = quota(client, headers)
    assert state["exempt"] and not state["limited"] and state["calls_left"] is None
    acid = new_conversation(client, headers)
    queue += [text_reply("三"), text_reply("四")]
    assert chat(client, headers, acid).status_code == 200
    assert chat(client, headers, acid).status_code == 200
    assert not queue


def test_admin_can_change_limits_and_see_usage(client, register, server_key):
    _, queue = server_key
    headers = admin_headers(client)
    view = body(client.get("/admin/settings", headers=headers))
    assert view["ai_daily_calls"] == settings.AI_DAILY_CALLS and view["ai_limit_source"]["calls"] == "env"

    saved = body(client.put("/admin/settings", headers=headers, json={"ai_daily_calls": 3, "ai_daily_tokens": 0}))
    assert saved["ai_daily_calls"] == 3 and saved["ai_daily_tokens"] == 0 and saved["ai_limit_source"]["calls"] == "admin"
    body(client.put("/admin/settings", headers=headers, json={"ai_daily_calls": -1}), 422)

    user_headers, user = register("用量最多的同学")
    assert quota(client, user_headers)["calls_left"] == 3
    cid = new_conversation(client, user_headers)
    queue.append(text_reply("好的", usage={"prompt_tokens": 9000, "completion_tokens": 999}))
    assert chat(client, user_headers, cid).status_code == 200

    usage = body(client.get("/admin/dashboard", headers=headers))["ai_usage"]
    assert usage["today"]["calls"] >= 1 and usage["last_7d"]["tokens"] >= 9999 and usage["limits"]["calls"] == 3
    top = usage["top_users"][0]
    assert top["user_id"] == user["id"] and top["tokens_7d"] == 9999 and top["calls_today"] == 1
    assert len(usage["trend"]) == 7 and usage["trend"][-1]["calls"] >= 1


def test_settings_page_shows_quota_without_consuming(client, auth, server_key):
    set_limits(calls=4, tokens=0)
    for _ in range(3):
        data = body(client.get("/ai/settings", headers=auth))
    assert data["resolved"]["quota"]["calls_left"] == 4
    assert quota(client, auth)["calls_used"] == 0
