"""
1.2 第一批：无日期任务（AI 提案 / 计划）、归档计划隐藏未完成任务、长备注、
我的反馈隐藏已处理的旧反馈、前端错误记录自动清理。
"""

from datetime import timedelta

from conftest import body

from app.ai import agent
from app.core import timeutil
from app.core.database import SessionLocal
from app.models import ClientError, Feedback


def future(days: int) -> str:
    return (timeutil.today() + timedelta(days=days)).isoformat()


# ---------------------------------------------------------------- 无日期任务
def test_clean_task_allows_empty_date_but_not_start_without_date():
    item, errors = agent.clean_task({"title": "Linux：命令行入门", "duration_minutes": 45})
    assert errors == [] and item["date"] is None and item["start_time"] is None
    _, errors = agent.clean_task({"title": "x", "duration_minutes": 45, "start_time": "19:00"})
    assert any("日期" in e for e in errors)
    _, errors = agent.clean_task({"title": "x", "duration_minutes": 45, "date": "2026-13-40"})
    assert any("日期格式" in e for e in errors)


def test_task_proposal_keeps_undated_items_last(client, auth):
    from app.models import User

    db = SessionLocal()
    try:
        me = db.query(User).order_by(User.id.desc()).first()
        proposal, result = agent.build_task_proposal(db, me, [
            {"title": "VMware：安装虚拟机", "duration_minutes": 60},
            {"title": "Linux：文件系统", "duration_minutes": 45, "date": future(2), "start_time": "20:00"},
        ], "VMware + Linux", "")
    finally:
        db.close()
    assert result["count"] == 2 and "丢弃" not in result["note"]
    assert [t["date"] for t in proposal["items"]] == [future(2), None]
    assert result["dates"] == [future(2)]


def test_apply_undated_tasks_go_to_inbox_and_plan_has_no_dates(client, auth):
    items = [{"key": "t0", "title": "VMware：安装虚拟机", "duration_minutes": 60, "date": None, "start_time": None}]
    data = body(client.post("/ai/proposals/apply", headers=auth, json={"kind": "tasks", "items": items, "title": "Linux 路线"}))
    assert data["ok_count"] == 1
    task = body(client.get(f"/task/detail/{data['results'][0]['id']}", headers=auth))
    assert task["due_date"] is None and task["start_time"] is None
    plan = data["plan"]
    assert plan["undated"] is True and plan["start_date"] is None and plan["remaining_days"] is None and plan["expired"] is False
    # 出现在"即将"（收集箱）里
    upcoming = body(client.get("/task/list", headers=auth, params={"view": "upcoming"}))
    assert any(t["id"] == task["id"] for t in upcoming["items"])


def test_plan_can_be_created_and_updated_without_dates(client, auth):
    created = body(client.post("/study-plans", headers=auth, json={"title": "长期：算法", "undated": True}))["plan"]
    assert created["undated"] and created["start_date"] is None and created["end_date"] is None
    dated = body(client.put(f"/study-plans/{created['id']}", headers=auth, json={"start_date": future(0), "end_date": future(6)}))
    assert dated["undated"] is False and dated["duration_days"] == 7
    cleared = body(client.put(f"/study-plans/{created['id']}", headers=auth, json={"undated": True}))
    assert cleared["undated"] and cleared["start_date"] is None
    # 不传 undated 时保持原来的默认（今天起 7 天）
    normal = body(client.post("/study-plans", headers=auth, json={"title": "普通计划"}))["plan"]
    assert normal["undated"] is False and normal["start_date"] == future(0) and normal["duration_days"] == 7


# ---------------------------------------------------------------- 归档
def test_archived_plan_hides_open_tasks_and_restore_brings_them_back(client, auth):
    plan = body(client.post("/study-plans", headers=auth, json={"title": "暂停的计划"}))["plan"]
    today = future(0)
    open_task = body(client.post("/task/create", headers=auth, json={"title": "未完成", "due_date": today, "plan_id": plan["id"]}))
    done_task = body(client.post("/task/create", headers=auth, json={"title": "已完成", "due_date": today, "plan_id": plan["id"]}))
    body(client.put(f"/task/complete/{done_task['id']}", headers=auth))

    def today_ids():
        return {t["id"] for t in body(client.get("/task/list", headers=auth, params={"view": "today"}))["items"]}

    assert {open_task["id"], done_task["id"]} <= today_ids()
    body(client.put(f"/study-plans/{plan['id']}", headers=auth, json={"status": "archived"}))
    ids = today_ids()
    assert open_task["id"] not in ids, "归档后未完成的任务不再出现在今天"
    assert done_task["id"] in ids, "已完成的任务照常保留"
    # 计划详情里仍能看到全部任务
    detail = body(client.get(f"/study-plans/{plan['id']}", headers=auth))
    assert {t["id"] for t in detail["tasks"]} == {open_task["id"], done_task["id"]}

    body(client.put(f"/study-plans/{plan['id']}", headers=auth, json={"status": "active"}))
    assert open_task["id"] in today_ids()


# ---------------------------------------------------------------- 备注长度
def test_task_note_up_to_2000_chars(client, auth):
    note = "学习资源：\n" + "· 视频 https://www.bilibili.com/video/BV1\n" * 40
    assert 1000 < len(note) <= 2000
    task = body(client.post("/task/create", headers=auth, json={"title": "长备注", "note": note}))
    assert task["note"] == note.strip() or task["note"] == note
    # 修改其他字段时原样保存长备注
    body(client.put(f"/task/update/{task['id']}", headers=auth, json={"title": "长备注（改名）", "note": note}))
    body(client.post("/task/create", headers=auth, json={"title": "太长", "note": "x" * 2001}), 422)


# ---------------------------------------------------------------- 我的反馈
def test_my_feedback_hides_settled_old_items(client, register):
    headers, _ = register("反馈同学")
    ids = [body(client.post("/feedback", headers=headers, json={"category": "bug", "content": f"第 {i} 条反馈内容"}))["id"] for i in range(3)]
    old = timeutil.now() - timedelta(days=8)
    db = SessionLocal()
    try:
        # 0：已解决、已读、8 天前 → 隐藏；1：已解决但回复未读 → 保留；2：待处理 → 保留
        settled = db.get(Feedback, ids[0])
        settled.status, settled.user_unread = "resolved", False
        unread = db.get(Feedback, ids[1])
        unread.status, unread.user_unread = "resolved", True
        db.flush()
        db.query(Feedback).filter(Feedback.id.in_(ids[:2])).update({"updated_at": old}, synchronize_session=False)
        db.commit()
    finally:
        db.close()
    mine = body(client.get("/feedback/mine", headers=headers))
    assert {item["id"] for item in mine["items"]} == {ids[1], ids[2]} and mine["hidden"] == 1
    everything = body(client.get("/feedback/mine", headers=headers, params={"all": True}))
    assert {item["id"] for item in everything["items"]} == set(ids) and everything["hidden"] == 0


# ---------------------------------------------------------------- 前端错误记录清理
def test_client_errors_older_than_90_days_are_pruned(client):
    from app.api.routes import admin

    db = SessionLocal()
    try:
        stale = ClientError(fingerprint="stale-fp", message="TypeError: old", count=3,
                            created_at=timeutil.now() - timedelta(days=120), last_seen=timeutil.now() - timedelta(days=91))
        fresh = ClientError(fingerprint="fresh-fp", message="TypeError: recent", count=1,
                            created_at=timeutil.now() - timedelta(days=10), last_seen=timeutil.now() - timedelta(days=10))
        db.add_all([stale, fresh])
        db.commit()
    finally:
        db.close()
    admin._last_prune["at"] = None
    body(client.post("/client-errors", json={"message": "TypeError: new", "stack": "at x", "page": "/"}))
    db = SessionLocal()
    try:
        prints = {row.fingerprint for row in db.query(ClientError).all()}
    finally:
        db.close()
    assert "stale-fp" not in prints and "fresh-fp" in prints
