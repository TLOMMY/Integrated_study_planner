# -*- coding: utf-8 -*-
"""专注记录、学习统计、排行榜。"""

from datetime import datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import func

from app.api.deps import DB, CurrentUser
from app.core import timeutil
from app.core.errors import ApiError, ok
from app.models import FocusRecord, StudyTask
from app.schemas import FocusIn
from app.services import gamification
from app.services.tasks import get_owned_task, task_to_dict

router = APIRouter(prefix="/study", tags=["专注与统计"])

DAILY_FOCUS_LIMIT = 16 * 60


@router.post("/record", summary="提交一次专注（按实际分钟计 XP，可关联任务）")
def record_focus(payload: FocusIn, user: CurrentUser, db: DB):
    task = get_owned_task(db, user, payload.task_id) if payload.task_id else None
    ended = timeutil.now()
    day = ended.date()
    started = None
    if payload.started_at:
        try:
            started = datetime.fromisoformat(payload.started_at[:19])
        except ValueError:
            started = None
    started = started or ended - timedelta(minutes=payload.duration_minutes)

    today_minutes = int(
        db.query(func.coalesce(func.sum(FocusRecord.duration_minutes), 0))
        .filter(FocusRecord.user_id == user.id, FocusRecord.record_date == day.isoformat())
        .scalar()
    )
    if today_minutes + payload.duration_minutes > DAILY_FOCUS_LIMIT:
        raise ApiError(422, "今天的专注时长已超过 16 小时，注意休息")

    tracker = gamification.RewardTracker(db, user)
    planned = payload.planned_minutes or payload.duration_minutes
    full = payload.completed and payload.duration_minutes >= planned
    record = FocusRecord(
        user_id=user.id,
        task_id=task.id if task else None,
        record_date=day.isoformat(),
        duration_minutes=payload.duration_minutes,
        planned_minutes=planned,
        completed=full,
        subject=payload.subject or (task.subject if task and task.subject else (task.title if task else None)),
        started_at=started,
        ended_at=ended,
        source="timer",
    )
    db.add(record)
    db.flush()

    room = max(0, gamification.FOCUS_XP_DAILY_CAP - gamification.focus_xp_today(db, user.id, day))
    gamification.award(db, user.id, min(room, payload.duration_minutes * gamification.XP_PER_FOCUS_MINUTE),
                       "focus", str(record.id), on=day)
    if full and planned >= 20:
        room = max(0, gamification.FOCUS_XP_DAILY_CAP - gamification.focus_xp_today(db, user.id, day))
        gamification.award(db, user.id, min(room, gamification.XP_POMODORO_BONUS), "pomodoro", str(record.id), on=day)
    if task:
        task.focus_minutes = int(task.focus_minutes or 0) + payload.duration_minutes
        if full and planned >= 20:
            task.pomodoros = int(task.pomodoros or 0) + 1
    gamification.maybe_award_daily_goal(db, user, day)
    reward = tracker.finish()
    db.commit()
    return ok(
        {
            "record": {
                "id": record.id,
                "duration_minutes": record.duration_minutes,
                "planned_minutes": record.planned_minutes,
                "completed": record.completed,
                "subject": record.subject,
                "record_date": record.record_date,
            },
            "task": task_to_dict(task) if task else None,
            "reward": reward,
        },
        "专注已记录",
    )


@router.get("/stats", summary="学习统计总览（等级、连续打卡、热力图、趋势、成就、排行榜）")
def stats(user: CurrentUser, db: DB):
    today = timeutil.today()
    minutes = gamification.focus_minutes_by_day(db, user.id, since=today - timedelta(days=13))
    tasks = gamification.completed_tasks_by_day(db, user.id, since=today - timedelta(days=13))
    week = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        key = day.isoformat()
        week.append({"date": key, "label": timeutil.weekday_label(day), "short": day.strftime("%m/%d"),
                     "minutes": minutes.get(key, 0), "tasks": tasks.get(key, 0)})
    this_week = sum(item["minutes"] for item in week)
    last_week = sum(minutes.get((today - timedelta(days=d)).isoformat(), 0) for d in range(7, 14))
    total_minutes = int(
        db.query(func.coalesce(func.sum(FocusRecord.duration_minutes), 0)).filter(FocusRecord.user_id == user.id).scalar()
    )
    sessions = db.query(func.count(FocusRecord.id)).filter(FocusRecord.user_id == user.id).scalar()
    done = db.query(func.count(StudyTask.id)).filter(StudyTask.user_id == user.id, StudyTask.completed.is_(True)).scalar()
    return ok(
        {
            "level": gamification.level_info(gamification.total_xp(db, user.id)),
            "streak": gamification.streak_info(db, user.id),
            "daily_goal": gamification.daily_goal_info(db, user),
            "totals": {
                "focus_minutes": total_minutes,
                "sessions": int(sessions or 0),
                "tasks_completed": int(done or 0),
                "active_days": len(gamification.active_days(db, user.id)),
            },
            "week": week,
            "week_minutes": this_week,
            "week_change": round((this_week - last_week) / last_week * 100) if last_week else None,
            "heatmap": gamification.heatmap(db, user.id),
            "subjects": gamification.subject_breakdown(db, user.id),
            "achievements": gamification.achievements_view(db, user.id),
            "leaderboard": gamification.weekly_leaderboard(db, user, limit=5),
        }
    )


@router.get("/leaderboard", summary="本周 XP 排行榜")
def leaderboard(user: CurrentUser, db: DB):
    return ok(gamification.weekly_leaderboard(db, user, limit=20))
