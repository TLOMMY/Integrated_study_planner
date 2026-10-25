# -*- coding: utf-8 -*-
"""专注记录、学习统计、排行榜、按科目统计、每周报告、专注跨设备同步。"""

import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter
from sqlalchemy import func

from app.api.deps import DB, CurrentUser
from app.core import timeutil
from app.core.errors import ApiError, ok
from app.models import FocusRecord, StudyTask, User
from app.schemas import FocusIn, FocusStateIn
from app.services import gamification
from app.services.tasks import get_owned_task, task_to_dict
from app.services.weekly_report import build_weekly_report

router = APIRouter(prefix="/study", tags=["专注与统计"])

DAILY_FOCUS_LIMIT = 16 * 60


@router.post("/record", summary="提交一次专注（按实际分钟计 XP，可关联任务）")
def record_focus(payload: FocusIn, user: CurrentUser, db: DB):
    focus_state = _load_focus_state(user)
    if payload.session_id and payload.session_id in (focus_state.get("recorded") or []):
        # 同一轮专注已由另一台设备提交过，不重复记录
        return ok({"record": None, "task": None, "reward": None, "duplicate": True}, "这轮专注已在其他设备上记录")
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
    if payload.session_id:
        _mark_recorded(user, focus_state, payload.session_id)
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


# ---------------------------------------------------------------- 按科目统计 / 每周报告
@router.get("/subjects", summary="按科目统计专注分钟与占比（days=7|30|90）")
def subjects(user: CurrentUser, db: DB, days: int = 30):
    if days not in (7, 30, 90):
        raise ApiError(422, "统计范围只能是 7、30 或 90 天")
    return ok(gamification.subject_stats(db, user.id, days=days))


@router.get("/weekly-report", summary="每周学习报告（week_start 为该周任意一天，默认本周）")
def weekly_report(user: CurrentUser, db: DB, week_start: Optional[str] = None):
    today = timeutil.today()
    day = timeutil.parse_date(week_start) if week_start else today
    if day is None:
        raise ApiError(422, "week_start 格式应为 YYYY-MM-DD")
    if timeutil.monday_of(day) > timeutil.monday_of(today):
        raise ApiError(422, "这一周还没有开始")
    return ok(build_weekly_report(db, user, day))


# ---------------------------------------------------------------- 专注跨设备同步
RECORDED_KEEP = 20


def _now_ms() -> int:
    return int(timeutil.now().timestamp() * 1000)


def _load_focus_state(user: User) -> dict:
    try:
        state = json.loads(user.focus_state or "{}")
        return state if isinstance(state, dict) else {}
    except (TypeError, ValueError):
        return {}


def _mark_recorded(user: User, state: dict, session_id: str) -> None:
    """记下已提交的会话 id；服务器上正是这一轮（或没有进行中的）时顺带清空进行中状态。"""
    recorded = [sid for sid in (state.get("recorded") or []) if sid != session_id] + [session_id]
    if state.get("session_id") in (None, session_id):
        state = {"status": "idle", "session_id": session_id, "device": state.get("device"),
                 "updated_at": max(int(state.get("updated_at") or 0) + 1, _now_ms())}
    state["recorded"] = recorded[-RECORDED_KEEP:]
    user.focus_state = json.dumps(state, ensure_ascii=False)


def _public_state(state: dict) -> Optional[dict]:
    if not state or state.get("status") not in ("running", "paused"):
        return None
    keys = ("status", "session_id", "task", "planned_minutes", "accumulated_ms", "segment_start",
            "started_at", "updated_at", "device")
    return {key: state.get(key) for key in keys}


@router.get("/focus-state", summary="进行中的专注（跨设备同步）；没有进行中的专注时 state 为 null")
def get_focus_state(user: CurrentUser):
    state = _load_focus_state(user)
    return ok({
        "state": _public_state(state),
        "session_id": state.get("session_id"),
        "updated_at": int(state.get("updated_at") or 0),
        "server_time": _now_ms(),
    })


@router.put("/focus-state", summary="上报本机专注状态；以 updated_at 较新的为准，idle/finished 表示结束并清空")
def put_focus_state(payload: FocusStateIn, user: CurrentUser, db: DB):
    state = _load_focus_state(user)
    stored_at = int(state.get("updated_at") or 0)
    recorded = state.get("recorded") or []
    stale = payload.updated_at <= stored_at
    # 已经记录过的会话不能再被"复活"成进行中
    revived = payload.status in ("running", "paused") and payload.session_id in recorded
    if stale or revived:
        return ok({"accepted": False, "state": _public_state(state), "session_id": state.get("session_id"),
                   "updated_at": stored_at}, "服务器上有更新的专注状态")
    if payload.status in ("running", "paused"):
        fresh = payload.model_dump()
    else:
        fresh = {"status": "idle", "session_id": payload.session_id, "updated_at": payload.updated_at,
                 "device": payload.device}
    fresh["recorded"] = recorded
    user.focus_state = json.dumps(fresh, ensure_ascii=False)
    db.commit()
    return ok({"accepted": True, "state": _public_state(fresh), "session_id": fresh.get("session_id"),
               "updated_at": payload.updated_at}, "专注状态已同步")
