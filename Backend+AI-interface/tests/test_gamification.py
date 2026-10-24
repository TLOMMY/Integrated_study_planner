from datetime import timedelta

from conftest import body

from app.core import timeutil
from app.core.database import SessionLocal
from app.models import FocusRecord
from app.services import gamification


def test_level_curve():
    assert gamification.level_info(0)["level"] == 1
    assert gamification.level_info(99)["level"] == 1
    assert gamification.level_info(100) == {"level": 2, "total_xp": 100, "xp_in_level": 0, "xp_for_next": 150, "progress": 0}
    assert gamification.level_info(249)["level"] == 2
    assert gamification.level_info(250)["level"] == 3


def test_focus_reward_and_daily_goal(client, auth):
    body(client.put("/users/me", headers=auth, json={"daily_goal_minutes": 30}))
    # 固定在白天专注，避免凌晨跑测试时额外触发"早起的鸟儿"成就
    noon = timeutil.now().replace(hour=14, minute=0, second=0, microsecond=0)
    first = body(client.post("/study/record", headers=auth, json={"duration_minutes": 25, "planned_minutes": 25,
                                                                 "started_at": noon.isoformat()}))
    reward = first["reward"]
    assert reward["xp_gained"] == 25 + 5 + 10  # 分钟 + 完整番茄 + 首次专注成就
    assert reward["goal_just_reached"] is False
    assert reward["streak"]["current"] == 1 and reward["streak"]["active_today"] is True

    second = body(client.post("/study/record", headers=auth, json={"duration_minutes": 10, "planned_minutes": 25,
                                                                  "completed": False}))
    assert second["record"]["completed"] is False
    assert second["reward"]["goal_just_reached"] is True
    assert second["reward"]["xp_gained"] >= 10 + 20  # 按实际分钟 + 每日目标，无番茄奖励


def test_focus_links_task(client, auth):
    task = body(client.post("/task/create", headers=auth, json={"title": "C++ 作业"}))
    data = body(client.post("/study/record", headers=auth, json={"task_id": task["id"], "duration_minutes": 25,
                                                                "planned_minutes": 25}))
    assert data["task"]["focus_minutes"] == 25 and data["task"]["pomodoros"] == 1
    assert data["record"]["subject"] == "C++ 作业"


def test_focus_validation(client, register):
    alice, _ = register()
    bob, _ = register()
    body(client.post("/study/record", headers=alice, json={"duration_minutes": 0}), 422)
    body(client.post("/study/record", headers=alice, json={"duration_minutes": 301}), 422)
    task = body(client.post("/task/create", headers=bob, json={"title": "bob"}))
    body(client.post("/study/record", headers=alice, json={"task_id": task["id"], "duration_minutes": 5}), 404)


def test_streak_counts_consecutive_days(client, register):
    _, user = register()
    today = timeutil.today()
    db = SessionLocal()
    try:
        for offset in (1, 2, 4):
            day = today - timedelta(days=offset)
            db.add(FocusRecord(user_id=user["id"], record_date=day.isoformat(), duration_minutes=30))
        db.commit()
        info = gamification.streak_info(db, user["id"])
        assert info["current"] == 2 and info["at_risk"] is True and info["active_today"] is False
        db.add(FocusRecord(user_id=user["id"], record_date=today.isoformat(), duration_minutes=30))
        db.commit()
        info = gamification.streak_info(db, user["id"])
        assert info["current"] == 3 and info["longest"] == 3 and info["at_risk"] is False
    finally:
        db.close()


def test_stats_and_leaderboard_shape(client, auth):
    body(client.post("/study/record", headers=auth, json={"duration_minutes": 20}))
    stats = body(client.get("/study/stats", headers=auth))
    assert len(stats["week"]) == 7 and stats["week"][-1]["minutes"] == 20
    assert len(stats["heatmap"]["days"]) >= 15 * 7
    assert len(stats["achievements"]) == len(gamification.ACHIEVEMENTS)
    board = body(client.get("/study/leaderboard", headers=auth))
    assert board["me"]["is_me"] is True and board["me"]["xp"] > 0
    # 正式账号的榜单里不出现演示同学，只和其他真实用户比
    assert not any(entry["is_demo"] for entry in board["entries"])
    demo = {"Authorization": "Bearer " + body(client.post("/auth/demo"))["access_token"]}
    demo_board = body(client.get("/study/leaderboard", headers=demo))
    assert any(entry["is_demo"] for entry in demo_board["entries"])


def test_home_summary(client, auth):
    data = body(client.get("/home/summary", headers=auth))
    for key in ("greeting", "task_counts", "daily_goal", "streak", "level", "courses"):
        assert key in data
