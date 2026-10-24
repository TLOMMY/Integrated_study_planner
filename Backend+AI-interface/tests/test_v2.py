"""第二版新增：账号安全、学习时段偏好、回收站、批量任务、搜索、反馈、AI 多轮记忆与日期范围。"""

from datetime import timedelta

from conftest import body

from app.ai.nlu import parse_request
from app.core import ratelimit, timeutil
from app.core.config import settings


def _task(client, headers, **extra):
    payload = {"title": "复习线性代数", "subject": "线性代数", "due_date": timeutil.today().isoformat(), **extra}
    return body(client.post("/task/create", headers=headers, json=payload))


# ---------------------------------------------------------------- 账号安全
def test_login_lockout_after_repeated_failures(client, register):
    _, user = register()
    for _ in range(settings.LOGIN_MAX_FAILS):
        body(client.post("/auth/login", json={"identifier": user["email"], "password": "wrong-pass"}), 401)
    locked = client.post("/auth/login", json={"identifier": user["email"], "password": "secret123"})
    assert locked.status_code == 429 and "分钟后再试" in locked.json()["message"]
    ratelimit.reset()
    body(client.post("/auth/login", json={"identifier": user["email"], "password": "secret123"}))


def test_password_change_revokes_other_sessions(client, register):
    old_headers, user = register()
    other = body(client.post("/auth/login", json={"identifier": user["email"], "password": "secret123"}))
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    fresh = body(client.put("/users/me/password", headers=old_headers,
                            json={"old_password": "secret123", "new_password": "newpass456"}))
    body(client.get("/users/me", headers=other_headers), 401)
    body(client.get("/users/me", headers={"Authorization": f"Bearer {fresh['access_token']}"}))
    body(client.put("/users/me/password", headers={"Authorization": f"Bearer {fresh['access_token']}"},
                    json={"old_password": "newpass456", "new_password": "newpass456"}), 400)


def test_email_phone_binding_and_logout_all(client, register):
    headers, user = register()
    _, other = register()
    body(client.put("/users/me/email", headers=headers, json={"email": other["email"], "password": "secret123"}), 400)
    body(client.put("/users/me/email", headers=headers, json={"email": "x@example.com", "password": "bad"}), 400)
    new_email = f"new_{user['email']}"
    me = body(client.put("/users/me/email", headers=headers, json={"email": new_email, "password": "secret123"}))
    assert me["email"] == new_email
    body(client.post("/auth/login", json={"identifier": new_email, "password": "secret123"}))

    body(client.put("/users/me/phone", headers=headers, json={"phone": "12345", "password": "secret123"}), 422)
    me = body(client.put("/users/me/phone", headers=headers, json={"phone": "138 0013 8000", "password": "secret123"}))
    assert me["phone"] == "13800138000" and me["phone_masked"] == "138****8000"
    assert body(client.put("/users/me/phone", headers=headers, json={"phone": "", "password": "secret123"}))["phone"] == ""

    renewed = body(client.post("/users/me/logout-all", headers=headers))
    body(client.get("/users/me", headers=headers), 401)
    body(client.get("/users/me", headers={"Authorization": f"Bearer {renewed['access_token']}"}))


def test_demo_account_cannot_change_credentials(client):
    demo = {"Authorization": "Bearer " + body(client.post("/auth/demo"))["access_token"]}
    body(client.put("/users/me/email", headers=demo, json={"email": "d@example.com", "password": "x"}), 403)
    body(client.request("DELETE", "/users/me", headers=demo, json={"password": "x"}), 403)


def test_export_and_delete_account(client, register):
    headers, user = register()
    _task(client, headers)
    exported = body(client.get("/users/me/export", headers=headers))
    assert exported["user"]["email"] == user["email"] and len(exported["study_tasks"]) == 1
    assert "hashed_password" not in exported["user"]
    body(client.request("DELETE", "/users/me", headers=headers, json={"password": "bad"}), 400)
    body(client.request("DELETE", "/users/me", headers=headers, json={"password": "secret123"}))
    body(client.post("/auth/login", json={"identifier": user["email"], "password": "secret123"}), 401)


# ---------------------------------------------------------------- 学习时段偏好
def test_study_prefs_profile_and_planner_uses_them(client, auth):
    data = body(client.get("/users/me/study-prefs", headers=auth))
    assert data["prefs"]["mode"] == "auto" and data["effective"]["source"] == "default"
    evening = timeutil.now().replace(hour=20, minute=0, second=0, microsecond=0) - timedelta(days=1)
    for _ in range(7):
        body(client.post("/study/record", headers=auth, json={"duration_minutes": 50, "started_at": evening.isoformat()}))
    data = body(client.get("/users/me/study-prefs", headers=auth))
    assert data["profile"]["ranked"][0] == "evening" and data["effective"]["segments"][0] == "evening"

    body(client.put("/users/me/study-prefs", headers=auth,
                    json={"mode": "custom", "segments": ["morning"], "avoid": ["morning"]}), 422)
    saved = body(client.put("/users/me/study-prefs", headers=auth,
                            json={"mode": "custom", "segments": ["morning"], "avoid": ["evening"],
                                  "earliest": "09:00", "latest": "21:00", "block_minutes": 30, "rest_minutes": 5}))
    assert saved["effective"]["source"] == "custom" and "避开晚上" in saved["effective"]["text"]
    start = (timeutil.today() + timedelta(days=1)).isoformat()
    draft = body(client.post("/ai/plan", headers=auth, json={"message": "每天复习高数两小时", "start_date": start, "days": 3}))
    assert draft["tasks"]
    for task in draft["tasks"]:
        assert "09:00" <= task["start_time"] < "17:30" and task["duration_minutes"] <= 35
    body(client.put("/users/me/study-prefs", headers=auth, json={"mode": "custom", "earliest": "20:00", "latest": "19:00"}), 422)


# ---------------------------------------------------------------- 回收站 / 批量 / 搜索
def test_plan_trash_restore_purge_and_hidden_tasks(client, auth):
    plans = [body(client.post("/study-plans", headers=auth, json={"title": f"计划{i}"}))["plan"] for i in range(3)]
    task = _task(client, auth, plan_id=plans[0]["id"])
    body(client.delete(f"/study-plans/{plans[0]['id']}", headers=auth))
    body(client.delete(f"/study-plans/{plans[1]['id']}", headers=auth))
    listing = body(client.get("/study-plans", headers=auth))
    assert listing["counts"]["trash"] == 2 and all(p["id"] == plans[2]["id"] for p in listing["items"])
    trash = body(client.get("/study-plans?status=trash", headers=auth))
    assert {p["id"] for p in trash["items"]} == {plans[0]["id"], plans[1]["id"]} and trash["items"][0]["purge_in_days"] == 30
    # 回收站计划里的任务不出现在今日列表和日程里
    today = body(client.get("/task/list?view=today", headers=auth))
    assert task["id"] not in {t["id"] for t in today["items"]}
    body(client.put(f"/study-plans/{plans[0]['id']}", headers=auth, json={"title": "改名"}), 409)

    body(client.post("/study-plans/trash/restore", headers=auth, json={"ids": [plans[0]["id"]]}))
    today = body(client.get("/task/list?view=today", headers=auth))
    assert task["id"] in {t["id"] for t in today["items"]}
    emptied = body(client.delete("/study-plans/trash", headers=auth))
    assert emptied["count"] == 1
    body(client.post("/study-plans/trash/restore", headers=auth, json={"ids": [plans[1]["id"]]}), 404)


def test_batch_move_delete_and_search(client, auth, register):
    timed = _task(client, auth, title="背单词 Unit3", start_time="19:30", duration_minutes=40)
    untimed = _task(client, auth, title="整理笔记", subject="大学物理")
    moved = body(client.post("/task/batch", headers=auth, json={"ids": [timed["id"], untimed["id"]], "action": "move", "shift_days": 1}))
    assert moved["count"] == 2
    tomorrow = (timeutil.today() + timedelta(days=1)).isoformat()
    detail = body(client.get(f"/task/detail/{timed['id']}", headers=auth))
    assert detail["due_date"] == tomorrow and detail["start_time"] == "19:30" and detail["duration_minutes"] == 40
    target = (timeutil.today() + timedelta(days=5)).isoformat()
    body(client.post("/task/batch", headers=auth, json={"ids": [untimed["id"]], "action": "move", "due_date": target}))
    assert body(client.get(f"/task/detail/{untimed['id']}", headers=auth))["due_date"] == target
    body(client.post("/task/batch", headers=auth, json={"ids": [untimed["id"]], "action": "move"}), 422)

    found = body(client.get("/task/list", headers=auth, params={"view": "all", "q": "物理"}))
    assert [t["id"] for t in found["items"]] == [untimed["id"]]

    other, _ = register()
    body(client.post("/task/batch", headers=other, json={"ids": [timed["id"]], "action": "delete"}), 404)
    body(client.post("/task/batch", headers=auth, json={"ids": [timed["id"], untimed["id"]], "action": "delete"}))
    body(client.get(f"/task/detail/{timed['id']}", headers=auth), 404)


# ---------------------------------------------------------------- 反馈
def test_feedback_saved_as_txt_and_admin_only(client, auth, register):
    saved = body(client.post("/feedback", headers=auth, json={"category": "bug", "content": "专注页偶尔白屏\n需要刷新", "page": "/focus-timer"}))
    path = settings.FEEDBACK_DIR / f"{saved['id']}.txt"
    text = path.read_text(encoding="utf-8")
    assert "功能异常" in text and "专注页偶尔白屏" in text and "/focus-timer" in text
    body(client.get("/feedback", headers=auth), 403)
    body(client.post("/feedback", headers=auth, json={"content": "短"}), 422)

    admin = client.post("/auth/register", json={"email": "admin@example.com", "password": "secret123"})
    token = admin.json()["data"]["access_token"] if admin.status_code == 200 else \
        body(client.post("/auth/login", json={"identifier": "admin@example.com", "password": "secret123"}))["access_token"]
    admin_headers = {"Authorization": f"Bearer {token}"}
    listing = body(client.get("/feedback", headers=admin_headers))
    assert any(item["id"] == saved["id"] for item in listing["items"])
    raw = client.get(f"/feedback/{saved['id']}", headers=admin_headers)
    assert raw.status_code == 200 and "专注页偶尔白屏" in raw.text
    body(client.get("/feedback/..%2F..%2Fmain", headers=admin_headers), 404)


# ---------------------------------------------------------------- AI：日期范围与多轮记忆
def test_nlu_explicit_date_ranges():
    ref = timeutil.today()
    year = ref.year

    def span(text):
        parsed = parse_request(text, ref, [])
        return parsed["start"], parsed["days"]

    start, days = span(f"12.1-12.10 复习高数")
    assert (start.month, start.day, days) == (12, 1, 10)
    start, days = span("12月1日到12月10日每天2小时")
    assert (start.month, start.day, days) == (12, 1, 10)
    start, days = span("12月1日-10日")
    assert (start.month, days) == (12, 10)
    start, days = span("12月3日起5天")
    assert (start.day, days) == (3, 5)
    # "作业2.3""1.5小时" 不是日期
    parsed = parse_request("概率论作业2.3每天1.5小时", ref, [])
    assert parsed["daily_minutes"] == 90 and not parsed["date_explicit"]
    assert year  # 年份自动补全，不必写死


def test_multi_turn_memory_changes_only_what_was_said(client, auth):
    start = timeutil.today() + timedelta(days=2)
    first = body(client.post("/ai/plan", headers=auth, json={
        "message": f"{start.month}月{start.day}日起3天每天复习线性代数1小时，晚上学"}))
    assert first["start_date"] == start.isoformat() and first["days"] == 3 and first["daily_minutes"] == 60
    memory = first["memory"]
    assert memory["subjects"] == ["线性代数"] and memory["prefer"] == "evening"

    new_start = start + timedelta(days=7)
    end = new_start + timedelta(days=4)
    second = body(client.post("/ai/plan", headers=auth, json={
        "message": f"改到{new_start.month}.{new_start.day}-{end.month}.{end.day}", "memory": memory,
        "history": [{"role": "user", "content": "第一轮"}, {"role": "assistant", "content": "计划摘要"}] * 10}))
    # 只换日期：科目、时长、时段沿用上一轮
    assert second["start_date"] == new_start.isoformat() and second["days"] == 5
    assert second["subjects"] == ["线性代数"] and second["daily_minutes"] == 60 and second["prefer"] == "evening"
    assert len({t["date"] for t in second["tasks"]}) >= 4
    assert len(second["memory"]["notes"]) == 2

    third = body(client.post("/ai/plan", headers=auth, json={"message": "加上英语", "memory": second["memory"]}))
    assert third["subjects"] == ["线性代数", "英语"] and third["start_date"] == new_start.isoformat()

    past = timeutil.today() - timedelta(days=10)
    body(client.post("/ai/plan", headers=auth, json={"message": "复习", "start_date": past.isoformat(), "days": 3}), 422)
