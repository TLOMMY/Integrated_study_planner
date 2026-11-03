"""
思考控制（结构化抽取默认关闭思考）、模型友好名与服务器 DeepSeek 的 Flash / Pro 选择、
课表识别默认用 Flash、AI 删除提案（批量、确认后逐条删除、撤销）。所有模型调用均为本地假响应。
"""

import json

import pytest
from conftest import body
from test_agent import chat, fake_model, future, new_conversation, text_reply, tool_reply, use_model  # noqa: F401
from test_import_ai import _recognize, text_pdf
from test_llm import completion, fake_llm  # noqa: F401

from app.ai import llm, providers
from app.core.config import settings


# ---------------------------------------------------------------- 思考控制
def test_thinking_body_only_for_deepseek():
    flash = llm.ModelConfig("https://api.deepseek.com/v1", "k", "deepseek-flash", thinking="max")
    other = llm.ModelConfig("https://x.com/v1", "k", "qwen-plus", thinking="high")
    assert llm.thinking_body(flash, False) == {"thinking": {"type": "disabled"}}
    assert llm.thinking_body(flash, True) == {"thinking": {"type": "enabled"}, "reasoning_effort": "max"}
    assert llm.thinking_body(flash, None) == {}
    assert llm.thinking_body(other, False) == {} and llm.thinking_body(other, True) == {}
    # 两个 DeepSeek 模型都支持思考；思考强度为 off 时流式也不开
    assert llm.supports_thinking(flash) and not llm.supports_thinking(other)
    assert not llm.supports_thinking(llm.ModelConfig("u", "k", "deepseek-v4-pro", thinking="off"))


def test_chat_json_disables_thinking_and_retries_without_it(fake_llm):  # noqa: F811
    from test_llm import http_error

    calls, queue = fake_llm
    config = llm.ModelConfig("https://api.deepseek.com/v1", "k", "deepseek-v4-pro")
    queue.append(completion('{"a": 1}'))
    assert llm.chat_json(config, [{"role": "user", "content": "x"}]) == {"a": 1}
    assert calls[-1]["body"]["thinking"] == {"type": "disabled"}
    # 兼容服务不认识思考参数（400）：去掉后重试
    queue += [http_error(400, "unknown field thinking"), completion('{"b": 2}')]
    assert llm.chat_json(config, [{"role": "user", "content": "x"}]) == {"b": 2}
    assert "thinking" not in calls[-1]["body"] and "response_format" not in calls[-1]["body"]
    # 非 DeepSeek 不传
    queue.append(completion('{"c": 3}'))
    llm.chat_json(llm.ModelConfig("https://x.com/v1", "k", "qwen-plus"), [{"role": "user", "content": "x"}])
    assert "thinking" not in calls[-1]["body"]


def test_stream_with_thinking_off_disables_it_for_deepseek(client, auth, fake_model):  # noqa: F811
    calls, queue = fake_model
    use_model(client, auth, model="deepseek-flash")
    body(client.put("/ai/settings", headers=auth, json={"thinking": "off"}))
    queue.append(text_reply("好的"))
    chat(client, auth, new_conversation(client, auth), "你好")
    assert calls[0]["thinking"] == {"type": "disabled"} and "reasoning_effort" not in calls[0]


# ---------------------------------------------------------------- 模型名称与服务器模型选择
def test_model_labels_and_env_model_choice(client, auth, monkeypatch):
    assert providers.model_label("deepseek-flash") == "DeepSeek V4.1 Flash（快）"
    assert providers.model_label("deepseek-v4-pro") == "DeepSeek V4 Pro（强）"
    assert providers.model_label("qwen-vl-max") == "qwen-vl-max"

    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-test")
    data = body(client.get("/ai/settings", headers=auth))
    assert data["env"]["configured"] and data["env"]["selected"] is None
    assert [m["key"] for m in data["env"]["models"]] == ["deepseek-flash", "deepseek-v4-pro"]
    assert data["resolved"]["model_label"] == providers.model_label(providers.env_model())
    # 课表识别默认 Flash（未明确选择时）
    assert data["import_label"].endswith("DeepSeek V4.1 Flash（快）")

    data = body(client.put("/ai/settings", headers=auth, json={"env_model": "deepseek-v4-pro"}))
    assert data["env"]["selected"] == "deepseek-v4-pro" and data["resolved"]["model"] == "deepseek-v4-pro"
    assert data["resolved"]["label"] == "DeepSeek（服务器配置） · DeepSeek V4 Pro（强）"
    assert data["import_label"].endswith("DeepSeek V4 Pro（强）"), "用户明确选了 Pro，识别也用 Pro"
    data = body(client.put("/ai/settings", headers=auth, json={"env_model": "deepseek-flash"}))
    assert data["resolved"]["model"] == "deepseek-flash"
    assert body(client.get("/ai/health", headers=auth))["model_label"] == "DeepSeek V4.1 Flash（快）"
    body(client.put("/ai/settings", headers=auth, json={"env_model": "gpt-4o"}), 422)


def test_import_uses_flash_without_thinking_for_server_deepseek(client, auth, fake_llm, monkeypatch):  # noqa: F811
    calls, queue = fake_llm
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "DEEPSEEK_MODEL", "deepseek-v4-pro")
    pdf = text_pdf(["Course Timetable", "Period   Monday", "1-2      Advanced Math", "         Wang A101 1-16"])
    queue.append(completion(json.dumps({"courses": [{"course_name": "Advanced Math", "day_of_week": 1,
                                                     "start_period": 1, "end_period": 2, "week_text": "1-16周"}]})))
    preview = body(_recognize(client, auth, "kb.pdf", pdf))
    sent = calls[-1]["body"]
    assert sent["model"] == "deepseek-flash" and sent["thinking"] == {"type": "disabled"}
    assert preview["model"] == "DeepSeek（服务器配置） · DeepSeek V4.1 Flash（快）"


# ---------------------------------------------------------------- AI 删除任务和课程
def _task(client, headers, title, day, start):
    return body(client.post("/task/create", headers=headers, json={
        "title": title, "due_date": day, "start_time": start, "duration_minutes": 45}))


def test_delete_proposal_batch_confirm_and_undo(client, register, fake_model):  # noqa: F811
    calls, queue = fake_model
    alice, _ = register()
    bob, _ = register()
    use_model(client, alice)
    tomorrow, later = future(1), future(4)
    mine = [_task(client, alice, "高数作业", tomorrow, "15:00"), _task(client, alice, "英语听力", tomorrow, "16:00")]
    keep = _task(client, alice, "物理预习", later, "15:00")
    other = _task(client, bob, "别人的任务", tomorrow, "15:00")
    course = body(client.post("/timetable", headers=alice, json={"course_name": "体育", "day_of_week": 4,
                                                                "start_period": 3, "end_period": 4}))

    cid = new_conversation(client, alice)
    queue += [
        tool_reply(("propose_deletes", {"summary": "删除明天的任务和周四的体育课",
                                        "task_filter": {"start": tomorrow, "end": tomorrow},
                                        "items": [{"target": "course", "id": course["id"]},
                                                  {"target": "task", "id": other["id"]},
                                                  {"target": "task", "id": mine[0]["id"]}]})),
        text_reply("已生成删除提案，确认后删除。"),
    ]
    _, reply = chat(client, alice, cid, "删掉明天所有任务，再删除周四的体育课")
    # 工具定义里有删除工具；修改工具不再提供 delete
    tools = {t["function"]["name"]: t for t in calls[0]["tools"]}
    assert "propose_deletes" in tools
    change_actions = tools["propose_changes"]["function"]["parameters"]["properties"]["items"]["items"]["properties"]["action"]
    assert change_actions["enum"] == ["update"]
    assert "propose_deletes" in calls[0]["messages"][0]["content"]

    proposal = reply["meta"]["proposals"][0]
    assert proposal["type"] == "deletes"
    titles = sorted(i["title"] for i in proposal["items"])
    assert titles == ["体育", "英语听力", "高数作业"], "按日期选出两条任务（去重）+ 课程；别人的任务不进提案"
    tool_result = json.loads([m for m in calls[1]["messages"] if m["role"] == "tool"][0]["content"])
    assert tool_result["tasks"] == 2 and tool_result["courses"] == 1 and tool_result["invalid"]

    # 确认删除（篡改：塞进别人的任务）
    items = [{k: i[k] for k in ("key", "target", "id", "title")} for i in proposal["items"]]
    items.append({"key": "d9", "target": "task", "id": other["id"]})
    data = body(client.post("/ai/proposals/apply", headers=alice, json={
        "kind": "deletes", "items": items, "message_id": reply["id"], "proposal_id": proposal["id"]}))
    results = {r["key"]: r for r in data["results"]}
    assert data["ok_count"] == 3 and not results["d9"]["ok"]
    assert all("undo" not in r for r in data["results"]), "撤销快照不返回给前端"
    assert all(r.get("can_undo") for r in data["results"] if r["ok"])
    assert client.get(f"/task/detail/{mine[0]['id']}", headers=alice).status_code == 404
    assert body(client.get(f"/task/detail/{keep['id']}", headers=alice))["title"] == "物理预习"
    assert body(client.get(f"/task/detail/{other['id']}", headers=bob))["title"] == "别人的任务"
    assert not [c for c in body(client.get("/timetable", headers=alice))["courses"] if c["course_name"] == "体育"]

    stored = body(client.get(f"/ai/conversations/{cid}/messages", headers=alice))["items"][-1]
    stored_results = stored["meta"]["proposals"][0]["results"]
    assert all("undo" not in r for r in stored_results.values()) and stored_results["d0"]["can_undo"]

    # 别人不能撤销我的删除
    body(client.post("/ai/proposals/undo", headers=bob, json={"message_id": reply["id"], "proposal_id": proposal["id"]}), 404)
    # 撤销全部：任务、课程原样恢复（原 id 未被占用时保留）
    data = body(client.post("/ai/proposals/undo", headers=alice, json={"message_id": reply["id"],
                                                                      "proposal_id": proposal["id"]}))
    assert data["ok_count"] == 3
    restored = body(client.get(f"/task/detail/{mine[0]['id']}", headers=alice))
    assert restored["title"] == "高数作业" and restored["start_time"] == "15:00" and restored["due_date"] == tomorrow
    assert [c for c in body(client.get("/timetable", headers=alice))["courses"] if c["course_name"] == "体育"]
    # 再撤销一次：没有可撤销的
    body(client.post("/ai/proposals/undo", headers=alice, json={"message_id": reply["id"],
                                                               "proposal_id": proposal["id"]}), 422)
    stored = body(client.get(f"/ai/conversations/{cid}/messages", headers=alice))["items"][-1]
    assert all(r.get("undone") for r in stored["meta"]["proposals"][0]["results"].values() if r["ok"])

    # 撤销后历史里给模型的说明
    queue.append(text_reply("好的"))
    chat(client, alice, cid, "谢谢")
    history = [m["content"] for m in calls[-1]["messages"] if m["role"] == "assistant"]
    assert any("删除提案" in h and "撤销 3 条" in h for h in history)


def test_delete_proposal_without_message_cannot_undo(client, auth):
    task = _task(client, auth, "临时任务", future(2), "10:00")
    data = body(client.post("/ai/proposals/apply", headers=auth, json={
        "kind": "deletes", "items": [{"key": "d0", "target": "task", "id": task["id"]}]}))
    assert data["results"][0]["ok"] and not data["results"][0].get("can_undo")
    assert client.get(f"/task/detail/{task['id']}", headers=auth).status_code == 404


@pytest.mark.parametrize("model", ["deepseek-v4-pro"])
def test_legacy_change_delete_still_works(client, auth, model):
    """旧消息里的修改提案仍可能带 action=delete：继续支持。"""
    task = _task(client, auth, "旧提案任务", future(3), "09:00")
    data = body(client.post("/ai/proposals/apply", headers=auth, json={
        "kind": "changes", "items": [{"key": "m0", "target": "task", "id": task["id"], "action": "delete"}]}))
    assert data["results"][0]["ok"]


def test_delete_and_undo_only_touch_active_timetable_set(client, auth):
    """多套课表：删除提案只认生效那套里的课；撤销恢复到当前生效那套。"""
    def courses():
        return {c["id"]: c["course_name"] for c in body(client.get("/timetable", headers=auth))["courses"]}

    body(client.post("/timetable", headers=auth, json={"course_name": "旧表体育", "day_of_week": 4,
                                                      "start_period": 5, "end_period": 6}))
    old_id = next(iter(courses()))
    old_set = next(s for s in body(client.get("/timetable/sets", headers=auth))["items"] if s["is_active"])
    body(client.post("/timetable/sets", headers=auth, json={"name": "新课表"}))  # 新建并切换
    new_set = next(s for s in body(client.get("/timetable/sets", headers=auth))["items"] if s["is_active"])
    assert new_set["id"] != old_set["id"] and courses() == {}
    body(client.post("/timetable", headers=auth, json={"course_name": "新表体育", "day_of_week": 4,
                                                      "start_period": 5, "end_period": 6}))
    new_id = next(iter(courses()))

    # 删除提案里不在生效课表的课被剔除；直接提交旧表课程也删不掉
    from app.ai import agent
    from app.core.database import SessionLocal
    from app.models import User
    session = SessionLocal()
    try:
        me = session.query(User).filter(User.id == body(client.get("/users/me", headers=auth))["id"]).first()
        proposal, result = agent.build_delete_proposal(session, me, [{"target": "course", "id": old_id},
                                                                     {"target": "course", "id": new_id}])
        assert [i["id"] for i in proposal["items"]] == [new_id] and result["invalid"]
    finally:
        session.close()
    data = body(client.post("/ai/proposals/apply", headers=auth, json={
        "kind": "deletes", "items": [{"key": "d0", "target": "course", "id": old_id}]}))
    assert not data["results"][0]["ok"]

    # 通过对话消息删除新表课程，切回旧表后撤销：课恢复到当前生效的那套（旧表）
    cid = new_conversation(client, auth)
    session = SessionLocal()
    try:
        import json as _json
        from app.models import ChatMessage
        me = session.query(User).filter(User.id == body(client.get("/users/me", headers=auth))["id"]).first()
        proposal, _ = agent.build_delete_proposal(session, me, [{"target": "course", "id": new_id}])
        message = ChatMessage(conversation_id=cid, user_id=me.id, role="assistant", content="删除提案",
                              meta=_json.dumps({"proposals": [proposal]}, ensure_ascii=False))
        session.add(message)
        session.commit()
        message_id = message.id
    finally:
        session.close()
    body(client.post("/ai/proposals/apply", headers=auth, json={
        "kind": "deletes", "items": [{"key": "d0", "target": "course", "id": new_id}],
        "message_id": message_id, "proposal_id": proposal["id"]}))
    assert courses() == {}
    body(client.post(f"/timetable/sets/{old_set['id']}/activate", headers=auth))
    assert set(courses().values()) == {"旧表体育"}
    body(client.post("/ai/proposals/undo", headers=auth, json={"message_id": message_id, "proposal_id": proposal["id"]}))
    assert set(courses().values()) == {"旧表体育", "新表体育"}, "恢复到当前生效的那套"
    body(client.post(f"/timetable/sets/{new_set['id']}/activate", headers=auth))
    assert courses() == {}, "其他套不受影响"
