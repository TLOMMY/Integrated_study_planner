from datetime import timedelta

from conftest import body

from app.core import timeutil


def _create(client, headers, **fields):
    payload = {"title": "复习高数", "duration_minutes": 45, **fields}
    return body(client.post("/task/create", headers=headers, json=payload))


def test_users_are_isolated(client, register):
    alice, _ = register("A")
    bob, _ = register("B")
    task = _create(client, alice, due_date=timeutil.today().isoformat())
    assert body(client.get(f"/task/detail/{task['id']}", headers=bob), 404) is None
    body(client.put(f"/task/complete/{task['id']}", headers=bob), 404)
    body(client.delete(f"/task/delete/{task['id']}", headers=bob), 404)
    assert all(item["id"] != task["id"] for item in body(client.get("/task/list", headers=bob))["items"])


def test_schedule_fields_and_midnight_guard(client, auth):
    today = timeutil.today().isoformat()
    task = _create(client, auth, due_date=today, start_time="19:30", duration_minutes=50, priority=3)
    assert (task["start_time"], task["end_time"], task["priority_label"]) == ("19:30", "20:20", "高")
    body(client.post("/task/create", headers=auth, json={"title": "熬夜", "due_date": today, "start_time": "23:40",
                                                        "duration_minutes": 60}), 422)
    # 只给时刻不给日期时归到今天
    assert _create(client, auth, start_time="08:00")["due_date"] == today


def test_views_today_overdue_upcoming(client, auth):
    today = timeutil.today()
    _create(client, auth, title="今天的", due_date=today.isoformat())
    _create(client, auth, title="昨天的", due_date=(today - timedelta(days=1)).isoformat())
    _create(client, auth, title="明天的", due_date=(today + timedelta(days=1)).isoformat())
    _create(client, auth, title="收集箱")
    titles = lambda view: {t["title"] for t in body(client.get(f"/task/list?view={view}", headers=auth))["items"]}  # noqa: E731
    assert titles("today") == {"今天的"}
    assert titles("overdue") == {"昨天的"}
    assert titles("upcoming") == {"明天的", "收集箱"}
    counts = body(client.get("/task/list", headers=auth))["counts"]
    assert counts["today"] == 1 and counts["overdue"] == 1 and counts["upcoming"] == 2


def test_complete_is_idempotent_and_reversible(client, auth):
    task = _create(client, auth, due_date=timeutil.today().isoformat())
    first = body(client.put(f"/task/complete/{task['id']}", headers=auth))
    reward = first["reward"]
    assert first["task"]["completed"] is True
    assert reward["xp_gained"] >= 10
    assert "first_task" in {a["code"] for a in reward["new_achievements"]}
    again = body(client.put(f"/task/complete/{task['id']}", headers=auth))
    assert again["reward"]["xp_gained"] == 0
    total = reward["level"]["total_xp"]
    undone = body(client.put(f"/task/uncomplete/{task['id']}", headers=auth))
    assert undone["task"]["completed"] is False
    assert undone["level"]["total_xp"] == total - 10


def test_repeat_task_spawns_next_once(client, auth):
    today = timeutil.today()
    task = _create(client, auth, title="背单词", due_date=today.isoformat(), start_time="07:30", repeat_rule="daily")
    result = body(client.put(f"/task/complete/{task['id']}", headers=auth))
    nxt = result["next_task"]
    assert nxt["due_date"] == (today + timedelta(days=1)).isoformat() and nxt["start_time"] == "07:30"
    body(client.put(f"/task/uncomplete/{task['id']}", headers=auth))
    again = body(client.put(f"/task/complete/{task['id']}", headers=auth))
    assert again["next_task"] is None


def test_partial_update_keeps_other_fields(client, auth):
    task = _create(client, auth, due_date=timeutil.today().isoformat(), start_time="14:00", priority=2)
    updated = body(client.put(f"/task/update/{task['id']}", headers=auth, json={"title": "改名"}))
    assert updated["title"] == "改名" and updated["start_time"] == "14:00" and updated["priority"] == 2
    cleared = body(client.put(f"/task/update/{task['id']}", headers=auth, json={"start_time": None}))
    assert cleared["start_time"] is None and cleared["due_date"] == task["due_date"]


def test_plan_completion_bonus_and_cascade(client, auth):
    plan = body(client.post("/study-plans", headers=auth, json={"title": "一周冲刺"}))["plan"]
    task = _create(client, auth, plan_id=plan["id"], due_date=timeutil.today().isoformat())
    reward = body(client.put(f"/task/complete/{task['id']}", headers=auth))["reward"]
    assert reward["xp_gained"] >= 10 + 30
    detail = body(client.get(f"/study-plans/{plan['id']}", headers=auth))
    assert detail["status"] == "completed" and detail["progress"] == 100
    # 带专注记录的任务所在计划也能删除（外键安全）
    body(client.post("/study/record", headers=auth, json={"task_id": task["id"], "duration_minutes": 5}))
    # 删除先进回收站，彻底删除时才连同任务一起删掉
    body(client.delete(f"/study-plans/{plan['id']}", headers=auth))
    purged = body(client.post("/study-plans/trash/purge", headers=auth, json={"ids": [plan["id"]]}))
    assert purged["deleted_tasks"] == 1
    body(client.get(f"/task/detail/{task['id']}", headers=auth), 404)


def test_cannot_attach_task_to_others_plan(client, register):
    alice, _ = register()
    bob, _ = register()
    plan = body(client.post("/study-plans", headers=alice, json={"title": "A 的计划"}))["plan"]
    body(client.post("/task/create", headers=bob, json={"title": "x", "plan_id": plan["id"]}), 404)
