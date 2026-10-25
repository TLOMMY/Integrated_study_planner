"""v4 · D：考试倒计时、学习小组、断签保护卡、每周报告、按科目统计、专注跨设备同步。"""

from datetime import timedelta

from conftest import body

from app.core import timeutil
from app.core.database import SessionLocal
from app.models import FocusRecord, StreakFreeze, User
from app.services import gamification


def _study(user_id, days):
    db = SessionLocal()
    try:
        for day in days:
            db.add(FocusRecord(user_id=user_id, record_date=day.isoformat(), duration_minutes=30, subject="高数"))
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------- 考试
def test_exam_crud_sorting_and_ownership(client, register):
    alice, _ = register()
    bob, _ = register()
    today = timeutil.today()
    far = body(client.post("/exams", headers=alice, json={"title": "线性代数期末", "exam_date": (today + timedelta(days=20)).isoformat()}))
    near = body(client.post("/exams", headers=alice, json={"title": "高数期中", "subject": "高等数学",
                                                         "exam_date": (today + timedelta(days=2)).isoformat(),
                                                         "start_time": "09:00", "location": "A1408"}))
    body(client.post("/exams", headers=alice, json={"title": "英语四级", "exam_date": (today - timedelta(days=3)).isoformat()}))
    data = body(client.get("/exams", headers=alice))
    assert [e["title"] for e in data["upcoming"]] == ["高数期中", "线性代数期末"]
    assert data["upcoming"][0]["days_left"] == 2 and data["upcoming"][0]["urgent"] is True
    assert data["upcoming"][1]["urgent"] is False
    assert [e["title"] for e in data["past"]] == ["英语四级"] and data["past"][0]["is_past"] is True

    updated = body(client.put(f"/exams/{far['id']}", headers=alice, json={"location": "B2203", "start_time": ""}))
    assert updated["location"] == "B2203" and updated["title"] == "线性代数期末" and updated["start_time"] == ""
    body(client.post("/exams", headers=alice, json={"title": "坏日期", "exam_date": "2026/01/01"}), 422)

    # 别人的考试看不到也改不了
    assert body(client.get("/exams", headers=bob))["upcoming"] == []
    body(client.put(f"/exams/{near['id']}", headers=bob, json={"title": "x"}), 404)
    body(client.delete(f"/exams/{near['id']}", headers=bob), 404)
    body(client.delete(f"/exams/{near['id']}", headers=alice))
    assert len(body(client.get("/exams", headers=alice))["upcoming"]) == 1


# ---------------------------------------------------------------- 学习小组
def test_group_join_leave_and_leaderboard(client, register):
    owner, owner_user = register("组长")
    member, member_user = register("组员")
    outsider, _ = register("路人")
    group = body(client.post("/groups", headers=owner, json={"name": "高数互助组"}))
    assert group["is_owner"] and group["member_count"] == 1 and len(group["invite_code"]) == 6

    joined = body(client.post("/groups/join", headers=member, json={"invite_code": group["invite_code"].lower()}))
    assert joined["member_count"] == 2 and joined["is_owner"] is False
    body(client.post("/groups/join", headers=member, json={"invite_code": group["invite_code"]}), 409)
    body(client.post("/groups/join", headers=outsider, json={"invite_code": "ZZZZZZ"}), 404)

    # 组员专注一次，组内排行第一；非组员看不到小组
    body(client.post("/study/record", headers=member, json={"duration_minutes": 30}))
    board = body(client.get(f"/groups/{group['id']}", headers=owner))["leaderboard"]
    assert [e["user_id"] for e in board["entries"]] == [member_user["id"], owner_user["id"]]
    assert board["entries"][0]["xp"] > 0 and board["entries"][1]["xp"] == 0 and board["me"]["rank"] == 2
    body(client.get(f"/groups/{group['id']}", headers=outsider), 404)
    assert body(client.get("/groups", headers=member))[0]["my_rank"] == 1

    # 只有组长能解散；组长退出后组长自动转给组员
    body(client.delete(f"/groups/{group['id']}", headers=member), 403)
    left = body(client.post(f"/groups/{group['id']}/leave", headers=owner))
    assert left["new_owner_id"] == member_user["id"] and left["dissolved"] is False
    assert body(client.get(f"/groups/{group['id']}", headers=member))["is_owner"] is True
    assert body(client.get("/groups", headers=owner)) == []
    body(client.delete(f"/groups/{group['id']}", headers=member))
    body(client.get(f"/groups/{group['id']}", headers=member), 404)


def test_last_member_leaving_dissolves_group(client, register):
    owner, _ = register()
    group = body(client.post("/groups", headers=owner, json={"name": "一个人的组"}))
    assert body(client.post(f"/groups/{group['id']}/leave", headers=owner))["dissolved"] is True
    body(client.post("/groups/join", headers=owner, json={"invite_code": group["invite_code"]}), 404)


# ---------------------------------------------------------------- 断签保护卡
def test_freeze_earned_after_seven_days(client, register):
    _, user = register()
    today = timeutil.today()
    _study(user["id"], [today - timedelta(days=i) for i in range(7)])
    db = SessionLocal()
    try:
        info = gamification.streak_info(db, user["id"])
        assert info["current"] == 7 and info["freezes"] == 1 and info["next_freeze_in"] == 7
        result = gamification.settle_freezes(db, db.get(User, user["id"]))
        db.commit()
        assert result["earned"] == [today.isoformat()]
        # 再结算一次不会重复发卡
        assert gamification.settle_freezes(db, db.get(User, user["id"])) == {"used": [], "earned": []}
        assert db.get(User, user["id"]).streak_freezes == 1
    finally:
        db.close()


def test_freeze_auto_consumed_and_counts_as_studied(client, register):
    headers, user = register()
    today = timeutil.today()
    # 连续学了 7 天（截止前天），昨天没学
    _study(user["id"], [today - timedelta(days=i) for i in range(2, 9)])
    db = SessionLocal()
    try:
        info = gamification.streak_info(db, user["id"])
        yesterday = (today - timedelta(days=1)).isoformat()
        assert info["current"] == 8 and info["at_risk"] is True and info["freezes"] == 0
        assert info["last_protected"] == yesterday and info["protected_days"] == [yesterday]
        assert any(d["frozen"] for d in info["week"]) or timeutil.monday_of(today) == today
    finally:
        db.close()

    # 今天专注一次：保护卡流水落库，连续天数 +1
    reward = body(client.post("/study/record", headers=headers, json={"duration_minutes": 20}))["reward"]
    assert reward["streak"]["current"] == 9 and reward["streak_freeze"]["used"] == [yesterday]
    data = body(client.get("/streak/freezes", headers=headers))
    kinds = {(h["day"], h["kind"]) for h in data["history"]}
    assert (yesterday, "used") in kinds and ((today - timedelta(days=2)).isoformat(), "earned") in kinds
    assert data["held"] == 0 and data["max"] == 3
    db = SessionLocal()
    try:
        rows = db.query(StreakFreeze).filter(StreakFreeze.user_id == user["id"]).count()
        assert rows == 2
    finally:
        db.close()


def test_freeze_not_used_when_gap_too_long(client, register):
    _, user = register()
    today = timeutil.today()
    _study(user["id"], [today - timedelta(days=i) for i in range(3, 6)])
    db = SessionLocal()
    try:
        u = db.get(User, user["id"])
        u.streak_freezes = 1
        db.commit()
        info = gamification.streak_info(db, user["id"])
        # 缺了 2 天、只有 1 张卡：补不满就不消耗，连续中断，卡还在
        assert info["current"] == 0 and info["freezes"] == 1 and info["last_protected"] is None
    finally:
        db.close()


def test_freeze_capped_at_three(client, register):
    _, user = register()
    today = timeutil.today()
    _study(user["id"], [today - timedelta(days=i) for i in range(14)])
    db = SessionLocal()
    try:
        u = db.get(User, user["id"])
        u.streak_freezes = 3
        db.commit()
        gamification.settle_freezes(db, u)
        db.commit()
        assert db.get(User, user["id"]).streak_freezes == 3
        kinds = sorted(k for (k,) in db.query(StreakFreeze.kind).filter(StreakFreeze.user_id == user["id"]))
        assert kinds == ["capped", "capped"]
        assert gamification.streak_info(db, user["id"])["current"] == 14
    finally:
        db.close()


# ---------------------------------------------------------------- 科目统计 / 周报
def test_subject_stats_and_weekly_report(client, register):
    headers, user = register()
    body(client.post("/study/record", headers=headers, json={"duration_minutes": 30, "subject": "高等数学"}))
    body(client.post("/study/record", headers=headers, json={"duration_minutes": 10, "subject": "英语"}))
    body(client.post("/study/record", headers=headers, json={"duration_minutes": 10}))
    task = body(client.post("/task/create", headers=headers, json={"title": "作业", "due_date": timeutil.today().isoformat()}))
    body(client.put(f"/task/complete/{task['id']}", headers=headers))

    data = body(client.get("/study/subjects?days=7", headers=headers))
    assert data["total_minutes"] == 50
    first = data["items"][0]
    assert first["subject"] == "高等数学" and first["minutes"] == 30 and first["percent"] == 60.0
    assert {i["subject"] for i in data["items"]} == {"高等数学", "英语", "自由专注"}
    body(client.get("/study/subjects?days=12", headers=headers), 422)

    report = body(client.get("/study/weekly-report", headers=headers))
    today = timeutil.today()
    assert report["week_start"] == timeutil.monday_of(today).isoformat() and report["is_current"] is True
    assert report["focus"]["total_minutes"] == 50 and report["focus"]["sessions"] == 3
    assert len(report["daily"]) == 7 and sum(d["minutes"] for d in report["daily"]) == 50
    assert report["tasks"]["completed"] == 1 and report["tasks"]["planned_done"] == 1
    assert report["xp"]["total"] > 0 and report["streak"]["current"] == 1
    assert any(a["code"] == "first_task" for a in report["achievements"])
    assert report["compare"]["focus_minutes"] is None  # 上周没有数据，不计算百分比
    last = body(client.get(f"/study/weekly-report?week_start={(today - timedelta(days=7)).isoformat()}", headers=headers))
    assert last["focus"]["total_minutes"] == 0 and last["is_complete"] is True and last["has_data"] is False
    body(client.get(f"/study/weekly-report?week_start={(today + timedelta(days=8)).isoformat()}", headers=headers), 422)


# ---------------------------------------------------------------- 专注跨设备同步
def _state(status, updated_at, **extra):
    return {"status": status, "session_id": "s-1", "planned_minutes": 25, "accumulated_ms": 0,
            "segment_start": updated_at, "updated_at": updated_at, "device": "电脑网页", **extra}


def test_focus_state_newer_wins_and_clears(client, register):
    headers, _ = register()
    other, _ = register()
    assert body(client.get("/study/focus-state", headers=headers))["state"] is None
    put = body(client.put("/study/focus-state", headers=headers, json=_state("running", 1000, task={"id": 1, "title": "高数"})))
    assert put["accepted"] is True
    got = body(client.get("/study/focus-state", headers=headers))
    assert got["state"]["status"] == "running" and got["state"]["task"]["title"] == "高数"
    # 别的账号互不影响
    assert body(client.get("/study/focus-state", headers=other))["state"] is None

    # 较旧的快照被拒绝，返回服务器上的较新状态
    stale = body(client.put("/study/focus-state", headers=headers, json=_state("paused", 900)))
    assert stale["accepted"] is False and stale["state"]["status"] == "running"
    newer = body(client.put("/study/focus-state", headers=headers, json=_state("paused", 2000, accumulated_ms=60000, device="手机")))
    assert newer["accepted"] and body(client.get("/study/focus-state", headers=headers))["state"]["device"] == "手机"

    # 结束后清空
    body(client.put("/study/focus-state", headers=headers, json=_state("idle", 3000)))
    assert body(client.get("/study/focus-state", headers=headers))["state"] is None


def test_focus_record_dedup_by_session(client, register):
    headers, _ = register()
    body(client.put("/study/focus-state", headers=headers, json=_state("running", 1000)))
    first = body(client.post("/study/record", headers=headers, json={"duration_minutes": 25, "session_id": "s-1"}))
    assert first["record"]["duration_minutes"] == 25
    # 记录后服务器上的进行中状态被清空，另一台设备再提交同一轮不会重复计
    assert body(client.get("/study/focus-state", headers=headers))["state"] is None
    again = body(client.post("/study/record", headers=headers, json={"duration_minutes": 25, "session_id": "s-1"}))
    assert again["duplicate"] is True and again["record"] is None
    # 已记录的会话不能被旧设备"复活"
    revive = body(client.put("/study/focus-state", headers=headers, json=_state("running", 99999999999999)))
    assert revive["accepted"] is False
    stats = body(client.get("/study/stats", headers=headers))
    assert stats["totals"]["sessions"] == 1
