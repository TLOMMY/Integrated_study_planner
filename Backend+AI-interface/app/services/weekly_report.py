# -*- coding: utf-8 -*-
"""
每周学习报告：专注总时长与每日分布、完成任务数、科目分布、连续天数、与上周对比、获得的 XP 与成就。

全部从流水现算（不缓存），过去的周数据不会再变化，本周的数据随学随更新。
F 的"每周 AI 复盘"可直接调用 build_weekly_report 拿统计。
"""

from datetime import date, timedelta
from typing import Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import timeutil
from app.models import FocusRecord, StudyTask, User, UserAchievement, XpEvent
from app.services import gamification

XP_REASONS = {
    "task": "完成任务",
    "focus": "专注时长",
    "pomodoro": "完整番茄",
    "daily_goal": "每日目标",
    "achievement": "成就奖励",
    "plan_complete": "完成计划",
}


def _change(now: int, before: int):
    return round((now - before) / before * 100) if before else None


def _week_numbers(db: Session, user_id: int, start: date, end: date) -> Dict[str, int]:
    s, e = start.isoformat(), end.isoformat()
    minutes = int(
        db.query(func.coalesce(func.sum(FocusRecord.duration_minutes), 0))
        .filter(FocusRecord.user_id == user_id, FocusRecord.record_date >= s, FocusRecord.record_date <= e)
        .scalar()
    )
    tasks = int(
        db.query(func.count(StudyTask.id))
        .filter(StudyTask.user_id == user_id, StudyTask.completed.is_(True),
                StudyTask.completed_at >= timeutil.combine(start, "00:00"),
                StudyTask.completed_at < timeutil.combine(end + timedelta(days=1), "00:00"))
        .scalar()
    )
    xp = int(
        db.query(func.coalesce(func.sum(XpEvent.amount), 0))
        .filter(XpEvent.user_id == user_id, XpEvent.event_date >= start, XpEvent.event_date <= end)
        .scalar()
    )
    days = {d for d in gamification.active_days(db, user_id) if start <= d <= end}
    return {"focus_minutes": minutes, "tasks_completed": tasks, "xp": xp, "active_days": len(days)}


def build_weekly_report(db: Session, user: User, week_start: date) -> dict:
    today = timeutil.today()
    start = timeutil.monday_of(week_start)
    end = start + timedelta(days=6)
    prev_start, prev_end = start - timedelta(days=7), start - timedelta(days=1)
    uid = user.id

    minutes = gamification.focus_minutes_by_day(db, uid, since=start)
    tasks = gamification.completed_tasks_by_day(db, uid, since=start)
    studied = gamification.active_days(db, uid)
    daily = []
    for i in range(7):
        day = start + timedelta(days=i)
        key = day.isoformat()
        daily.append({
            "date": key,
            "label": timeutil.weekday_label(day),
            "short": day.strftime("%m/%d"),
            "minutes": minutes.get(key, 0),
            "tasks": tasks.get(key, 0),
            "active": day in studied,
            "future": day > today,
        })

    s, e = start.isoformat(), end.isoformat()
    sessions = (
        db.query(FocusRecord.duration_minutes, FocusRecord.planned_minutes, FocusRecord.completed)
        .filter(FocusRecord.user_id == uid, FocusRecord.record_date >= s, FocusRecord.record_date <= e)
        .all()
    )
    pomodoros = sum(1 for _m, planned, done in sessions if done and (planned or 0) >= 20)
    planned_tasks = int(
        db.query(func.count(StudyTask.id))
        .filter(StudyTask.user_id == uid, StudyTask.due_date >= s, StudyTask.due_date <= e)
        .scalar()
    )
    due_done = int(
        db.query(func.count(StudyTask.id))
        .filter(StudyTask.user_id == uid, StudyTask.due_date >= s, StudyTask.due_date <= e,
                StudyTask.completed.is_(True))
        .scalar()
    )

    xp_rows = (
        db.query(XpEvent.reason, func.sum(XpEvent.amount))
        .filter(XpEvent.user_id == uid, XpEvent.event_date >= start, XpEvent.event_date <= end)
        .group_by(XpEvent.reason)
        .all()
    )
    xp_breakdown = sorted(
        ({"reason": reason, "label": XP_REASONS.get(reason, reason), "xp": int(total or 0)} for reason, total in xp_rows),
        key=lambda item: -item["xp"],
    )
    unlocked = (
        db.query(UserAchievement.code, UserAchievement.unlocked_at)
        .filter(UserAchievement.user_id == uid,
                UserAchievement.unlocked_at >= timeutil.combine(start, "00:00"),
                UserAchievement.unlocked_at < timeutil.combine(end + timedelta(days=1), "00:00"))
        .order_by(UserAchievement.unlocked_at)
        .all()
    )
    achievements = [
        {"code": code, "title": item.title, "icon": item.icon, "xp": item.xp,
         "unlocked_at": at.isoformat() if at else None}
        for code, at in unlocked
        if (item := gamification.ACHIEVEMENT_MAP.get(code))
    ]

    this = _week_numbers(db, uid, start, end)
    before = _week_numbers(db, uid, prev_start, prev_end)
    streak_ref = min(end, today)
    streak = gamification.streak_info(db, uid, ref=streak_ref)
    best = max(daily, key=lambda d: d["minutes"])
    return {
        "week_start": s,
        "week_end": e,
        "is_complete": end < today,
        "is_current": start <= today <= end,
        "focus": {
            "total_minutes": this["focus_minutes"],
            "sessions": len(sessions),
            "pomodoros": pomodoros,
            "daily_average": round(this["focus_minutes"] / 7),
            "best_day": best if best["minutes"] else None,
        },
        "daily": daily,
        "tasks": {
            "completed": this["tasks_completed"],
            "planned": planned_tasks,
            "planned_done": due_done,
            "completion_rate": round(due_done / planned_tasks * 100) if planned_tasks else None,
        },
        "subjects": gamification.subject_stats(db, uid, days=7, ref=end)["items"],
        "streak": {
            "current": streak["current"],
            "longest": streak["longest"],
            "active_days": this["active_days"],
            "protected_days": [d for d in streak["protected_days"] if s <= d <= e],
        },
        "xp": {"total": this["xp"], "breakdown": xp_breakdown},
        "achievements": achievements,
        "previous": {"week_start": prev_start.isoformat(), **before},
        "compare": {
            "focus_minutes": _change(this["focus_minutes"], before["focus_minutes"]),
            "tasks_completed": _change(this["tasks_completed"], before["tasks_completed"]),
            "xp": _change(this["xp"], before["xp"]),
            "active_days": this["active_days"] - before["active_days"],
        },
        "has_data": bool(this["focus_minutes"] or this["tasks_completed"] or this["xp"]),
        "generated_at": timeutil.now().isoformat(),
    }
