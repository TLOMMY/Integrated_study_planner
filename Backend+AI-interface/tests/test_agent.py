"""
AI 智能体：工具调用循环、追问、任务 / 课程 / 修改三类提案、逐条导入与失败原因、降级、会话 CRUD、SSE 格式。
所有模型调用都由本地假服务应答（支持 tools 回合与 SSE 分片），不访问外网。
"""

import io
import json
import urllib.error
from datetime import timedelta

import pytest
from conftest import body

from app.ai import llm
from app.core import timeutil


# ---------------------------------------------------------------- 假的 OpenAI 兼容服务
class FakeStream:
    """模拟 HTTPResponse：readline 逐行返回 SSE。"""

    def __init__(self, lines):
        self._lines = [line.encode("utf-8") for line in lines]

    def readline(self):
        return self._lines.pop(0) if self._lines else b""

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def sse(*chunks):
    lines = []
    for chunk in chunks:
        lines += [f"data: {json.dumps(chunk, ensure_ascii=False)}\n", "\n"]
    return FakeStream(lines + ["data: [DONE]\n", "\n"])


def delta(**fields):
    return {"choices": [{"index": 0, "delta": fields}]}


def text_reply(text, reasoning=None):
    """把一段文字切成多片流式下发，可带思考片段。"""
    chunks = []
    if reasoning:
        chunks += [delta(reasoning_content=reasoning[:5]), delta(reasoning_content=reasoning[5:])]
    chunks += [delta(content=text[i:i + 4]) for i in range(0, len(text), 4)]
    chunks.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                   "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    return sse(*chunks)


def tool_reply(*calls, reasoning="先查一下数据"):
    """一个或多个工具调用；arguments 拆成两片下发，验证分片拼接。"""
    chunks = [delta(reasoning_content=reasoning)]
    for index, (name, args) in enumerate(calls):
        raw = json.dumps(args, ensure_ascii=False)
        half = len(raw) // 2
        chunks.append(delta(tool_calls=[{"index": index, "id": f"call_{name}_{index}", "type": "function",
                                         "function": {"name": name, "arguments": raw[:half]}}]))
        chunks.append(delta(tool_calls=[{"index": index, "function": {"arguments": raw[half:]}}]))
    chunks.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]})
    return sse(*chunks)


def http_error(code, message="bad"):
    return urllib.error.HTTPError("http://x", code, "err", {},
                                  io.BytesIO(json.dumps({"error": {"message": message}}).encode()))


class Plain:
    def __init__(self, payload):
        self._data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def fake_model(monkeypatch):
    calls, queue = [], []

    def urlopen(request, timeout=None):
        calls.append(json.loads(request.data) if request.data else None)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)
    return calls, queue


def use_model(client, headers, model="deepseek-v4-pro"):
    body(client.post("/ai/providers", headers=headers, json={
        "name": "测试 DeepSeek", "base_url": "https://m.example.com/v1", "model": model, "api_key": "sk-x"}))


def new_conversation(client, headers):
    return body(client.post("/ai/conversations", headers=headers, json={}))["id"]


def parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        name, data = None, None
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if name:
            events.append((name, data))
    return events


def chat(client, headers, cid, message):
    response = client.post(f"/ai/conversations/{cid}/chat", headers=headers, json={"message": message})
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert events[-1][0] == "done", events
    return events, events[-1][1]["message"]


def future(days):
    return (timeutil.today() + timedelta(days=days)).isoformat()


# ---------------------------------------------------------------- 工具循环 + 提案
def test_tool_loop_then_task_proposal_and_sse_format(client, auth, fake_model):
    calls, queue = fake_model
    use_model(client, auth)
    cid = new_conversation(client, auth)
    day = future(3)
    queue += [
        tool_reply(("get_context", {}), ("get_free_slots", {"start": day, "end": day})),
        tool_reply(("propose_tasks", {"title": "线代复习", "items": [
            {"date": day, "start_time": "19:00", "duration_minutes": 45, "title": "线代：矩阵", "subject": "线代",
             "links": [{"title": "网课", "url": "https://www.bilibili.com/video/BV1", "source": "bilibili"},
                       {"title": "坏链接", "url": "javascript:alert(1)"}]},
            {"date": day, "start_time": "03:00", "duration_minutes": 45, "title": "线代：凌晨"},
        ]})),
        text_reply("给你排了两个学习块，确认后导入。", reasoning="同学要复习线代"),
    ]
    events, reply = chat(client, auth, cid, "帮我排一下线代复习")
    names = [e[0] for e in events]
    assert {"status", "reasoning", "text", "tool", "proposal", "done"} <= set(names)
    tools = [e[1] for e in events if e[0] == "tool" and e[1]["status"] == "done"]
    assert [t["name"] for t in tools] == ["get_context", "get_free_slots", "propose_tasks"]
    assert "".join(e[1]["delta"] for e in events if e[0] == "text").strip() == "给你排了两个学习块，确认后导入。"

    proposal = reply["meta"]["proposals"][0]
    assert proposal["type"] == "tasks" and len(proposal["items"]) == 2
    early, evening = proposal["items"]
    assert early["start_time"] == "03:00" and early["warnings"], "偏好以外的时间要标黄"
    assert evening["links"] == [{"title": "网课", "url": "https://www.bilibili.com/video/BV1", "source": "bilibili"}]
    assert reply["meta"]["reasoning"].startswith("先查一下数据")
    assert reply["meta"]["engine"] == "agent"

    # 思考模式参数、工具定义、带工具调用的助手回合回传 reasoning_content
    first = calls[0]
    assert first["stream"] is True and first["thinking"] == {"type": "enabled"} and first["reasoning_effort"] == "high"
    assert {t["function"]["name"] for t in first["tools"]} >= {"get_context", "propose_tasks", "ask_user"}
    assistant = [m for m in calls[1]["messages"] if m["role"] == "assistant" and m.get("tool_calls")][0]
    assert assistant["reasoning_content"] == "先查一下数据"
    assert json.loads(assistant["tool_calls"][1]["function"]["arguments"]) == {"start": day, "end": day}
    tool_msg = [m for m in calls[1]["messages"] if m["role"] == "tool"]
    assert len(tool_msg) == 2 and "free" in tool_msg[1]["content"]

    # 消息已存服务器
    stored = body(client.get(f"/ai/conversations/{cid}/messages", headers=auth))["items"]
    assert [m["role"] for m in stored] == ["user", "assistant"]
    assert stored[1]["meta"]["proposals"][0]["id"] == proposal["id"]


def test_interim_text_before_tool_call_moves_to_reasoning(client, auth, fake_model):
    _, queue = fake_model
    use_model(client, auth)
    cid = new_conversation(client, auth)
    queue += [
        sse(delta(content="我来查一下。"),
            delta(tool_calls=[{"index": 0, "id": "c1", "type": "function", "function": {"name": "get_context", "arguments": "{}"}}])),
        text_reply("今天适合复习高数。"),
    ]
    events, reply = chat(client, auth, cid, "今天学什么")
    assert reply["content"] == "今天适合复习高数。"
    assert "【过程】我来查一下。" in reply["meta"]["reasoning"]
    assert any(e[0] == "text" and e[1].get("replace") == "" for e in events)


def test_ask_user_ends_turn_without_proposal(client, auth, fake_model):
    calls, queue = fake_model
    use_model(client, auth)
    cid = new_conversation(client, auth)
    queue.append(tool_reply(("ask_user", {"question": "想复习哪一门？", "options": ["高数", "线代", "英语"]})))
    events, reply = chat(client, auth, cid, "帮我安排复习")
    assert len(calls) == 1, "追问后本轮立即结束"
    proposals = reply["meta"]["proposals"]
    assert [p["type"] for p in proposals] == ["ask"]
    assert proposals[0]["options"] == ["高数", "线代", "英语"]

    # 下一轮：模型能在历史里看到自己的追问
    queue.append(text_reply("好的，线代。"))
    chat(client, auth, cid, "线代")
    history = calls[-1]["messages"]
    assert any("[追问] 想复习哪一门" in m.get("content", "") for m in history if m["role"] == "assistant")
    assert history[-1] == {"role": "user", "content": "线代"}


def test_tasks_and_courses_are_separate_proposals(client, auth, fake_model):
    _, queue = fake_model
    use_model(client, auth)
    cid = new_conversation(client, auth)
    day = future(4)
    queue += [
        tool_reply(("propose_courses", {"items": [{"course_name": "数据库选修", "day_of_week": 4, "start_period": 11,
                                                   "end_period": 12, "week_text": "1-16周", "classroom": "A101"}]}),
                   ("propose_tasks", {"items": [{"date": day, "start_time": "20:00", "duration_minutes": 40,
                                                 "title": "数据库：预习"}]})),
        text_reply("课程和预习都安排好了。"),
    ]
    _, reply = chat(client, auth, cid, "我周四晚上 11-12 节有一门数据库选修，1-16 周，顺便排个预习")
    kinds = {p["type"]: p for p in reply["meta"]["proposals"]}
    assert set(kinds) == {"tasks", "courses"}
    course = kinds["courses"]["items"][0]
    assert course["weeks"] == list(range(1, 17)) and course["start_time"] == "20:40" and not course["warnings"]


# ---------------------------------------------------------------- 导入：逐条校验
def _timed_course(client, auth, day_iso, start_period, end_period, name="大学物理"):
    weekday = timeutil.parse_date(day_iso).isoweekday()
    body(client.post("/timetable", headers=auth, json={"course_name": name, "day_of_week": weekday,
                                                      "start_period": start_period, "end_period": end_period}))


def test_apply_tasks_reports_each_failure(client, auth):
    day = future(5)
    _timed_course(client, auth, day, 9, 10)  # 19:00-20:35
    items = [
        {"key": "t0", "date": day, "start_time": "15:00", "duration_minutes": 45, "title": "高数：真题"},
        {"key": "t1", "date": day, "start_time": "19:30", "duration_minutes": 30, "title": "改到上课时间"},
        {"key": "t2", "date": day, "start_time": "15:30", "duration_minutes": 30, "title": "和第一条重叠"},
        {"key": "t3", "date": day, "start_time": "23:40", "duration_minutes": 60, "title": "跨午夜"},
        {"key": "t4", "date": "2000-01-01", "start_time": "10:00", "duration_minutes": 30, "title": "过去"},
        {"key": "t5", "date": day, "start_time": "16:00", "duration_minutes": 30, "title": "英语：单词",
         "links": [{"title": "视频", "url": "https://b23.tv/x"}]},
    ]
    data = body(client.post("/ai/proposals/apply", headers=auth, json={"kind": "tasks", "items": items, "title": "冲刺"}))
    results = {r["key"]: r for r in data["results"]}
    assert results["t0"]["ok"] and results["t5"]["ok"]
    assert "大学物理" in results["t1"]["reason"] and "冲突" in results["t1"]["reason"]
    assert "本次导入" in results["t2"]["reason"]
    assert "午夜" in results["t3"]["reason"]
    assert "已经过去" in results["t4"]["reason"]
    assert data["ok_count"] == 2 and data["fail_count"] == 4
    # 学习资源链接写进备注（统一在备注里查看），不再单独存 links
    linked = body(client.get(f"/task/detail/{results['t5']['id']}", headers=auth))
    assert "学习资源" in linked["note"] and "https://b23.tv/x" in linked["note"] and linked["links"] == []
    assert data["plan"]["source"] == "ai" and data["plan"]["task_total"] == 2
    assert data["reward"] is not None

    # 重试失败条目：追加到同一个计划
    retry = body(client.post("/ai/proposals/apply", headers=auth, json={
        "kind": "tasks", "plan_id": data["plan"]["id"],
        "items": [{**items[1], "start_time": "21:00"}]}))
    assert retry["results"][0]["ok"] and retry["plan"]["id"] == data["plan"]["id"]
    assert retry["plan"]["task_total"] == 3


def test_apply_courses_conflict_and_bounds(client, auth):
    body(client.post("/timetable", headers=auth, json={"course_name": "操作系统", "day_of_week": 2,
                                                      "start_period": 3, "end_period": 4}))
    items = [
        {"key": "c0", "course_name": "编译原理", "day_of_week": 2, "start_period": 4, "end_period": 5, "week_text": "1-8周"},
        {"key": "c1", "course_name": "数据库", "day_of_week": 4, "start_period": 11, "end_period": 12, "week_text": "1-16周"},
        {"key": "c2", "course_name": "超节次", "day_of_week": 5, "start_period": 12, "end_period": 14},
        {"key": "c3", "course_name": "超周次", "day_of_week": 5, "start_period": 1, "end_period": 2, "week_text": "18-25周"},
        {"key": "c4", "course_name": "撞上数据库", "day_of_week": 4, "start_period": 12, "end_period": 12},
    ]
    data = body(client.post("/ai/proposals/apply", headers=auth, json={"kind": "courses", "items": items}))
    results = {r["key"]: r for r in data["results"]}
    assert "操作系统" in results["c0"]["reason"]
    assert results["c1"]["ok"]
    assert "节次表" in results["c2"]["reason"]
    assert "周次越界" in results["c3"]["reason"]
    assert "数据库" in results["c4"]["reason"]


# ---------------------------------------------------------------- 修改已有内容
def test_change_tasks_via_chat_and_ownership(client, register, fake_model):
    _, queue = fake_model
    alice, _ = register()
    bob, _ = register()
    use_model(client, alice)
    tomorrow, after = future(1), future(2)
    created = [body(client.post("/task/create", headers=alice, json={
        "title": title, "due_date": tomorrow, "start_time": start, "duration_minutes": 45}))
        for title, start in (("高数作业", "15:00"), ("英语听力", "16:00"))]
    other = body(client.post("/task/create", headers=bob, json={"title": "别人的任务", "due_date": tomorrow}))

    cid = new_conversation(client, alice)
    queue += [
        tool_reply(("list_tasks", {"start": tomorrow, "end": tomorrow})),
        tool_reply(("propose_changes", {"items": [
            {"target": "task", "id": created[0]["id"], "action": "update", "changes": {"date": after}},
            {"target": "task", "id": created[1]["id"], "action": "update", "changes": {"date": after}},
            {"target": "task", "id": other["id"], "action": "delete"},
        ]})),
        text_reply("已为你生成修改提案。"),
    ]
    _, reply = chat(client, alice, cid, "把明天的任务都往后挪一天")
    proposal = reply["meta"]["proposals"][0]
    assert proposal["type"] == "changes" and len(proposal["items"]) == 2, "别人的任务 id 不进提案"
    assert proposal["items"][0]["diff"][0]["field"] == "时间"

    # 前端篡改：把别人的任务塞进提交
    items = [{k: i[k] for k in ("key", "target", "id", "action", "changes")} for i in proposal["items"]]
    items.append({"key": "m9", "target": "task", "id": other["id"], "action": "delete"})
    data = body(client.post("/ai/proposals/apply", headers=alice, json={
        "kind": "changes", "items": items, "message_id": reply["id"], "proposal_id": proposal["id"]}))
    results = {r["key"]: r for r in data["results"]}
    assert results["m0"]["ok"] and results["m1"]["ok"]
    assert not results["m9"]["ok"] and "不存在" in results["m9"]["reason"]
    assert body(client.get(f"/task/detail/{other['id']}", headers=bob))["title"] == "别人的任务"
    moved = body(client.get(f"/task/detail/{created[0]['id']}", headers=alice))
    assert moved["due_date"] == after and moved["start_time"] == "15:00"

    # 结果写回消息，刷新后仍能看到
    stored = body(client.get(f"/ai/conversations/{cid}/messages", headers=alice))["items"][-1]
    assert stored["meta"]["proposals"][0]["applied"] is True
    assert stored["meta"]["proposals"][0]["results"]["m0"]["ok"] is True


def test_change_conflict_and_course_update(client, auth):
    day = future(6)
    _timed_course(client, auth, day, 1, 2, name="线代")  # 08:00-09:35
    task = body(client.post("/task/create", headers=auth, json={"title": "背单词", "due_date": day,
                                                               "start_time": "15:00", "duration_minutes": 30}))
    course = body(client.get("/timetable", headers=auth))["courses"][0]
    items = [
        {"key": "m0", "target": "task", "id": task["id"], "action": "update", "changes": {"start_time": "08:30"}},
        {"key": "m1", "target": "course", "id": course["id"], "action": "update",
         "changes": {"classroom": "B203", "start_period": 3, "end_period": 4}},
    ]
    results = body(client.post("/ai/proposals/apply", headers=auth, json={"kind": "changes", "items": items}))["results"]
    assert not results[0]["ok"] and "线代" in results[0]["reason"]
    assert results[1]["ok"] and "教室" in results[1]["summary"]
    updated = [c for c in body(client.get("/timetable", headers=auth))["courses"] if c["id"] == course["id"]][0]
    assert updated["classroom"] == "B203" and updated["start_period"] == 3


# ---------------------------------------------------------------- 降级
def test_tools_unsupported_falls_back_to_json_draft(client, auth, fake_model):
    calls, queue = fake_model
    use_model(client, auth, model="old-model")
    cid = new_conversation(client, auth)
    day = future(2)
    queue += [
        http_error(400, "tools is not supported for this model"),
        Plain({"choices": [{"message": {"content": json.dumps({
            "advice": "- 先看例题", "title": "物理复习",
            "tasks": [{"date": day, "start_time": "15:00", "duration_minutes": 45, "title": "物理：力学"}]},
            ensure_ascii=False)}}]}),
    ]
    _, reply = chat(client, auth, cid, f"{day} 复习物理")
    assert "thinking" not in calls[0], "不支持思考的模型不传思考参数"
    assert reply["meta"]["engine"] == "draft" and "不支持工具调用" in reply["meta"]["notice"]
    assert reply["meta"]["proposals"][0]["type"] == "tasks"
    assert "response_format" in calls[1]


def test_rule_engine_without_model(client, auth, fake_model):
    calls, _ = fake_model
    cid = new_conversation(client, auth)
    _, reply = chat(client, auth, cid, "这周每天一小时复习英语")
    assert reply["meta"]["engine"] == "rule" and reply["meta"]["proposals"][0]["type"] == "tasks"
    _, reply = chat(client, auth, cid, "我周四 11-12 节有一门数据库选修")
    assert not reply["meta"]["proposals"] and "大模型" in reply["content"]
    _, reply = chat(client, auth, cid, "把明天的任务往后挪一天")
    assert not reply["meta"]["proposals"] and "大模型" in reply["content"]
    assert calls == []


def test_model_failure_mid_stream_falls_back(client, auth, fake_model):
    _, queue = fake_model
    use_model(client, auth)
    cid = new_conversation(client, auth)
    queue += [http_error(503), http_error(503)]  # 重试一次仍失败
    _, reply = chat(client, auth, cid, "明天复习高数")
    assert reply["meta"]["engine"] == "rule" and "规则引擎" in reply["meta"]["notice"]


class ResetStream(FakeStream):
    """先下发几行，然后连接被重置。"""

    def readline(self):
        if not self._lines:
            raise ConnectionResetError(10054, "远程主机强迫关闭了一个现有的连接")
        return self._lines.pop(0)


def test_connection_reset_mid_stream_is_retried(client, auth, fake_model):
    calls, queue = fake_model
    use_model(client, auth)
    cid = new_conversation(client, auth)
    queue += [
        tool_reply(("get_context", {})),
        ResetStream([f"data: {json.dumps(delta(reasoning_content='想想'))}\n", "\n"]),
        text_reply("好的，已经看过你的安排。"),
    ]
    events, reply = chat(client, auth, cid, "看看我今天的安排")
    assert len(calls) == 3 and not reply["meta"].get("error")
    assert reply["content"].endswith("好的，已经看过你的安排。")
    assert any(e[0] == "status" and "重试" in e[1]["text"] for e in events)


# ---------------------------------------------------------------- 会话
def test_conversation_crud_and_isolation(client, register):
    alice, _ = register()
    bob, _ = register()
    cid = new_conversation(client, alice)
    assert body(client.get("/ai/conversations", headers=alice))["items"][0]["id"] == cid
    renamed = body(client.patch(f"/ai/conversations/{cid}", headers=alice, json={"title": "期末复习"}))
    assert renamed["title"] == "期末复习"
    for method, path in (("get", f"/ai/conversations/{cid}"), ("get", f"/ai/conversations/{cid}/messages"),
                         ("delete", f"/ai/conversations/{cid}")):
        body(getattr(client, method)(path, headers=bob), 404)
    body(client.patch(f"/ai/conversations/{cid}", headers=bob, json={"title": "x"}), 404)
    body(client.post(f"/ai/conversations/{cid}/chat", headers=bob, json={"message": "hi"}), 404)
    assert body(client.get("/ai/conversations", headers=bob))["items"] == []

    imported = body(client.post("/ai/conversations/import", headers=alice, json={
        "messages": [{"role": "user", "content": "旧问题"}, {"role": "assistant", "content": "旧回答"}]}))
    assert imported["title"] == "之前的对话" and imported["message_count"] == 2

    body(client.delete(f"/ai/conversations/{cid}", headers=alice))
    body(client.get(f"/ai/conversations/{cid}", headers=alice), 404)


def test_first_message_titles_conversation_and_sync_endpoint(client, auth, fake_model):
    _, queue = fake_model
    use_model(client, auth)
    cid = new_conversation(client, auth)
    queue.append(text_reply("线代先把行列式和矩阵运算吃透，再刷习题。"))
    data = body(client.post(f"/ai/conversations/{cid}/chat/sync", headers=auth, json={"message": "线代怎么复习"}))
    assert data["message"]["content"].startswith("线代先把") and not data["message"]["meta"]["proposals"]
    assert data["conversation"]["title"] == "线代怎么复习"


def test_thinking_setting(client, auth):
    use_model(client, auth)
    data = body(client.put("/ai/settings", headers=auth, json={"thinking": "max"}))
    assert data["providers"][0]["thinking"] == "max" and data["resolved"]["thinking"] == "max"
    body(client.put("/ai/settings", headers=auth, json={}), 422)
    deepseek = [p for p in data["presets"] if p["key"] == "deepseek"][0]
    assert deepseek["model"] == "deepseek-v4-pro"
