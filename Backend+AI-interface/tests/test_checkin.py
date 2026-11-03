"""打卡规则——当天专注 ≥ 5 分钟或完成 ≥ 1 个任务；连续天数、热力图、周报、保护卡口径一致。"""

from datetime import timedelta

from conftest import body

from app.core import timeutil
from app.core.database import SessionLocal
from app.models import FocusRecord
from app.services import gamification, weekly_report


def _focus(user_id, day, minutes):
    db = SessionLocal()
    try:
        db.add(FocusRecord(user_id=user_id, record_date=day.isoformat(), duration_minutes=minutes))
        db.commit()
    finally:
        db.close()


def test_rule_constants():
    assert gamification.STREAK_MIN_FOCUS == 5 and gamification.STREAK_MIN_TASKS == 1
    assert gamification.is_checked_in(5, 0) and gamification.is_checked_in(0, 1)
    assert not gamification.is_checked_in(4, 0) and not gamification.is_checked_in(0, 0)
    assert "5 分钟" in gamification.STREAK_RULE_TEXT and "1 个任务" in gamification.STREAK_RULE_TEXT


def test_short_focus_does_not_count_but_task_does(client, register):
    headers, user = register()
    today = timeutil.today()
    uid = user["id"]
    # 前天 3 分钟（不算）、昨天 2+3 分钟累计 5（算）
    _focus(uid, today - timedelta(days=2), 3)
    _focus(uid, today - timedelta(days=1), 2)
    _focus(uid, today - timedelta(days=1), 3)

    info = body(client.get("/study/stats", headers=headers))["streak"]
    assert info["current"] == 1 and info["active_today"] is False and info["at_risk"] is True
    assert info["rule"]["min_focus_minutes"] == 5 and info["today"]["checked_in"] is False
    assert info["today"]["focus_needed"] == 5

    # 今天专注 4 分钟：还差 1 分钟，没打卡
    body(client.post("/study/record", headers=headers, json={"duration_minutes": 4}))
    info = body(client.get("/study/stats", headers=headers))["streak"]
    assert info["active_today"] is False and info["today"]["focus_needed"] == 1

    # 完成 1 个任务即打卡
    task = body(client.post("/task/create", headers=headers, json={"title": "背单词", "due_date": today.isoformat()}))
    reward = body(client.put(f"/task/complete/{task['id']}", headers=headers))["reward"]
    assert reward["streak"]["current"] == 2 and reward["streak"]["active_today"] is True
    assert reward["streak"]["today"] == {"date": today.isoformat(), "focus_minutes": 4, "tasks_done": 1,
                                         "checked_in": True, "focus_needed": 0}

    # 热力图同一口径：3 分钟那天不上色
    stats = body(client.get("/study/stats", headers=headers))
    days = {d["date"]: d for d in stats["heatmap"]["days"]}
    assert days[(today - timedelta(days=2)).isoformat()]["level"] == 0
    assert days[(today - timedelta(days=2)).isoformat()]["checked_in"] is False
    assert days[(today - timedelta(days=1)).isoformat()]["level"] == 1
    assert days[today.isoformat()]["checked_in"] is True
    assert stats["heatmap"]["rule"]["text"] == gamification.STREAK_RULE_TEXT


def test_weekly_report_and_freeze_use_same_rule(client, register):
    _, user = register()
    uid = user["id"]
    today = timeutil.today()
    # 连续 7 天每天 4 分钟：一天都不算，不发保护卡
    for i in range(7):
        _focus(uid, today - timedelta(days=i), 4)
    db = SessionLocal()
    try:
        info = gamification.streak_info(db, uid)
        assert info["current"] == 0 and info["freezes"] == 0
        assert gamification.active_days(db, uid) == set()
        start = timeutil.monday_of(today)
        assert weekly_report._week_numbers(db, uid, start, today)["active_days"] == 0
    finally:
        db.close()
