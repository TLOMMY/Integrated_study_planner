# -*- coding: utf-8 -*-
"""
成长体系（对标多邻国）：XP / 等级 / 连续打卡 / 每日目标 / 成就 / 排行榜 / 热力图。

所有统计都从 focus_records、study_tasks、xp_events 现算，不存冗余字段，
因此不会出现"缓存的连续天数和真实记录对不上"的问题。
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Set

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import timeutil
from app.models import FocusRecord, ImportLog, StreakFreeze, StudyPlan, StudyTask, User, UserAchievement, XpEvent

# ---------------------------------------------------------------- XP 规则
XP_TASK = 10
XP_TASK_HIGH = 15
XP_PER_FOCUS_MINUTE = 1
XP_POMODORO_BONUS = 5
XP_DAILY_GOAL = 20
XP_PLAN_COMPLETE = 30
FOCUS_XP_DAILY_CAP = 300


@dataclass(frozen=True)
class Achievement:
    code: str
    title: str
    description: str
    icon: str
    metric: str
    target: int
    xp: int


ACHIEVEMENTS: List[Achievement] = [
    Achievement("first_task", "初出茅庐", "完成第 1 个任务", "lucide:sprout", "tasks_completed", 1, 10),
    Achievement("task_10", "行动派", "累计完成 10 个任务", "lucide:list-checks", "tasks_completed", 10, 30),
    Achievement("task_50", "任务收割机", "累计完成 50 个任务", "lucide:swords", "tasks_completed", 50, 80),
    Achievement("first_focus", "第一个番茄", "完成第 1 次专注", "lucide:timer", "focus_sessions", 1, 10),
    Achievement("focus_10h", "十小时定律", "累计专注 10 小时", "lucide:hourglass", "focus_minutes", 600, 50),
    Achievement("focus_50h", "专注大师", "累计专注 50 小时", "lucide:brain", "focus_minutes", 3000, 150),
    Achievement("marathon", "马拉松", "单日专注满 4 小时", "lucide:flame-kindling", "max_day_minutes", 240, 40),
    Achievement("early_bird", "早起的鸟儿", "在早上 8 点前开始专注", "lucide:sunrise", "early_sessions", 1, 20),
    Achievement("streak_3", "三天打鱼", "连续学习 3 天", "lucide:flame", "longest_streak", 3, 20),
    Achievement("streak_7", "一周不断", "连续学习 7 天", "lucide:zap", "longest_streak", 7, 50),
    Achievement("streak_30", "月度坚持", "连续学习 30 天", "lucide:crown", "longest_streak", 30, 200),
    Achievement("goal_5", "目标达人", "累计 5 天达成每日目标", "lucide:target", "goal_days", 5, 40),
    Achievement("planner", "计划通", "创建第 1 个学习计划", "lucide:map", "plans_created", 1, 10),
    Achievement("ai_planner", "AI 搭档", "采纳 1 份 AI 生成的计划", "lucide:sparkles", "ai_plans", 1, 20),
    Achievement("importer", "课表搬家", "成功导入一次课表", "lucide:file-spreadsheet", "imports", 1, 20),
]
ACHIEVEMENT_MAP: Dict[str, Achievement] = {item.code: item for item in ACHIEVEMENTS}


# ---------------------------------------------------------------- 等级
def level_cost(level: int) -> int:
    """从 level 升到 level+1 需要的 XP：100, 150, 200 ……"""
    return 100 + (level - 1) * 50


def level_info(total_xp: int) -> dict:
    level, remaining = 1, max(0, int(total_xp))
    while remaining >= level_cost(level):
        remaining -= level_cost(level)
        level += 1
    need = level_cost(level)
    return {
        "level": level,
        "total_xp": int(total_xp),
        "xp_in_level": remaining,
        "xp_for_next": need,
        "progress": round(remaining / need * 100),
    }


def total_xp(db: Session, user_id: int) -> int:
    return int(db.query(func.coalesce(func.sum(XpEvent.amount), 0)).filter(XpEvent.user_id == user_id).scalar())


def award(db: Session, user_id: int, amount: int, reason: str, ref: str, on: Optional[date] = None) -> int:
    """幂等发放 XP，同一 (reason, ref) 只记一次；返回实际发放数量。"""
    if amount <= 0:
        return 0
    exists = db.query(XpEvent.id).filter_by(user_id=user_id, reason=reason, ref=ref).first()
    if exists:
        return 0
    db.add(XpEvent(user_id=user_id, amount=amount, reason=reason, ref=ref, event_date=on or timeutil.today()))
    db.flush()
    return amount


def revoke(db: Session, user_id: int, reason: str, ref: str) -> int:
    event = db.query(XpEvent).filter_by(user_id=user_id, reason=reason, ref=ref).first()
    if not event:
        return 0
    amount = event.amount
    db.delete(event)
    db.flush()
    return amount


def focus_xp_today(db: Session, user_id: int, day: date) -> int:
    return int(
        db.query(func.coalesce(func.sum(XpEvent.amount), 0))
        .filter(XpEvent.user_id == user_id, XpEvent.event_date == day, XpEvent.reason.in_(["focus", "pomodoro"]))
        .scalar()
    )


# ---------------------------------------------------------------- 活跃天与连续打卡
def focus_minutes_by_day(db: Session, user_id: int, since: Optional[date] = None) -> Dict[str, int]:
    query = db.query(FocusRecord.record_date, func.sum(FocusRecord.duration_minutes)).filter(
        FocusRecord.user_id == user_id
    )
    if since:
        query = query.filter(FocusRecord.record_date >= since.isoformat())
    return {str(day): int(total or 0) for day, total in query.group_by(FocusRecord.record_date).all()}


def completed_tasks_by_day(db: Session, user_id: int, since: Optional[date] = None) -> Dict[str, int]:
    query = db.query(StudyTask.completed_at).filter(
        StudyTask.user_id == user_id, StudyTask.completed.is_(True), StudyTask.completed_at.isnot(None)
    )
    if since:
        query = query.filter(StudyTask.completed_at >= timeutil.combine(since, "00:00"))
    counts: Dict[str, int] = defaultdict(int)
    for (completed_at,) in query.all():
        counts[completed_at.date().isoformat()] += 1
    return counts


def active_days(db: Session, user_id: int) -> Set[date]:
    days = {date.fromisoformat(d) for d, minutes in focus_minutes_by_day(db, user_id).items() if minutes > 0}
    days |= {date.fromisoformat(d) for d in completed_tasks_by_day(db, user_id)}
    return days


# ---------------------------------------------------------------- 断签保护卡
FREEZE_EVERY = 7
FREEZE_MAX = 3


@dataclass
class FreezePlan:
    """断签保护卡的推演结果：已落库的流水 + 本次推演新增的（尚未落库）。"""

    held: int
    used: Set[date]
    new_used: List[date]
    new_earned: List[date]
    new_capped: List[date]


def _freeze_rows(db: Session, user_id: int) -> Dict[date, str]:
    rows = db.query(StreakFreeze.day, StreakFreeze.kind).filter(StreakFreeze.user_id == user_id).all()
    result = {}
    for day, kind in rows:
        parsed = timeutil.parse_date(day)
        if parsed:
            result[parsed] = kind or "used"
    return result


def plan_freezes(db: Session, user_id: int, ref: Optional[date] = None, days: Optional[Set[date]] = None) -> FreezePlan:
    """
    推演断签保护卡（纯计算，不写库）：
    1. 连续学习（只算真实学习日，保护日不算）每满 7 的倍数天获得 1 张，最多持有 3 张；
    2. 今天之前有缺勤缺口、且持有的卡够补满整个缺口时，自动逐天消耗补上；
       不够补满就不消耗（补了也保不住连续记录，卡留着下次用）。
    结果只依赖学习记录与已落库的流水，同一输入多次推演结果相同。
    """
    ref = ref or timeutil.today()
    active = days if days is not None else active_days(db, user_id)
    rows = _freeze_rows(db, user_id)
    user = db.get(User, user_id)
    held = int(getattr(user, "streak_freezes", 0) or 0)
    used = {d for d, kind in rows.items() if kind == "used"}
    processed = {d for d, kind in rows.items() if kind in ("earned", "capped")}
    plan = FreezePlan(held=held, used=set(used), new_used=[], new_earned=[], new_capped=[])

    def covered(day: date) -> bool:
        return day in active or day in plan.used

    def earn_run(end: date) -> None:
        """以 end 结尾的连续段里，补发尚未处理的"满 7 天"奖励。"""
        if not covered(end):
            return
        start = end
        while covered(start - timedelta(days=1)):
            start -= timedelta(days=1)
        count, cursor = 0, start
        while cursor <= end:
            if cursor in active:
                count += 1
                if count % FREEZE_EVERY == 0 and cursor not in processed:
                    processed.add(cursor)
                    if plan.held < FREEZE_MAX:
                        plan.held += 1
                        plan.new_earned.append(cursor)
                    else:
                        plan.new_capped.append(cursor)
            cursor += timedelta(days=1)

    history = [d for d in (active | plan.used) if d < ref]
    if history:
        last = max(history)
        gap = (ref - last).days - 1
        if gap <= FREEZE_MAX:
            earn_run(last)
        if 0 < gap <= plan.held:
            for offset in range(1, gap + 1):
                day = last + timedelta(days=offset)
                plan.used.add(day)
                plan.new_used.append(day)
                plan.held -= 1
    earn_run(ref)
    return plan


def settle_freezes(db: Session, user: User, ref: Optional[date] = None) -> dict:
    """把推演出的保护卡变化落库（只在会提交事务的写操作里调用，如完成任务、记录专注）。"""
    plan = plan_freezes(db, user.id, ref)
    if not (plan.new_used or plan.new_earned or plan.new_capped):
        return {"used": [], "earned": []}
    for kind, items in (("used", plan.new_used), ("earned", plan.new_earned), ("capped", plan.new_capped)):
        for day in items:
            db.add(StreakFreeze(user_id=user.id, day=day.isoformat(), kind=kind))
    user.streak_freezes = plan.held
    db.flush()
    return {"used": [d.isoformat() for d in plan.new_used], "earned": [d.isoformat() for d in plan.new_earned]}


def streak_info(db: Session, user_id: int, ref: Optional[date] = None) -> dict:
    """
    连续打卡：今天或昨天有学习即保持连续；被断签保护卡补上的日子视为已学习。
    at_risk=True 表示"昨天之前一直连着，今天还没学"，前端会提醒用户别断火。
    本函数只读：保护卡的消耗与获得在这里按规则推演出来，由 settle_freezes 在写操作中落库。
    """
    ref = ref or timeutil.today()
    studied = active_days(db, user_id)
    plan = plan_freezes(db, user_id, ref, studied)
    days = studied | plan.used
    active_today = ref in studied

    cursor = ref if active_today else ref - timedelta(days=1)
    current = 0
    protected = []
    while cursor in days:
        current += 1
        if cursor not in studied:
            protected.append(cursor)
        cursor -= timedelta(days=1)

    longest, run, previous = 0, 0, None
    for day in sorted(days):
        run = run + 1 if previous and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day

    week_start = timeutil.monday_of(ref)
    week = [
        {
            "date": (week_start + timedelta(days=i)).isoformat(),
            "label": timeutil.WEEKDAY_CN[i],
            "active": (week_start + timedelta(days=i)) in studied,
            "frozen": (week_start + timedelta(days=i)) in plan.used and (week_start + timedelta(days=i)) not in studied,
            "is_today": week_start + timedelta(days=i) == ref,
        }
        for i in range(7)
    ]
    # 本轮连续里最近一次被保护卡补上的日子（前端据此提示"已用保护卡保住连续记录"）
    last_protected = max(protected).isoformat() if protected else None
    studied_in_run = current - len(protected)
    return {
        "current": current,
        "longest": max(longest, current),
        "active_today": active_today,
        "at_risk": current > 0 and not active_today,
        "week": week,
        "freezes": plan.held,
        "freeze_max": FREEZE_MAX,
        "protected_days": sorted(d.isoformat() for d in protected),
        "last_protected": last_protected,
        "next_freeze_in": FREEZE_EVERY - studied_in_run % FREEZE_EVERY,
    }


# ---------------------------------------------------------------- 每日目标
def daily_goal_info(db: Session, user: User, day: Optional[date] = None) -> dict:
    day = day or timeutil.today()
    minutes = focus_minutes_by_day(db, user.id, since=day).get(day.isoformat(), 0)
    goal = int(user.daily_goal_minutes or 60)
    return {
        "date": day.isoformat(),
        "goal_minutes": goal,
        "done_minutes": minutes,
        "progress": min(100, round(minutes / goal * 100)) if goal else 0,
        "reached": minutes >= goal,
    }


# ---------------------------------------------------------------- 成就
def _metrics(db: Session, user_id: int) -> Dict[str, int]:
    by_day = focus_minutes_by_day(db, user_id)
    goal_days = (
        db.query(func.count(XpEvent.id)).filter(XpEvent.user_id == user_id, XpEvent.reason == "daily_goal").scalar()
    )
    early = (
        db.query(FocusRecord.started_at)
        .filter(FocusRecord.user_id == user_id, FocusRecord.started_at.isnot(None))
        .all()
    )
    return {
        "tasks_completed": db.query(func.count(StudyTask.id))
        .filter(StudyTask.user_id == user_id, StudyTask.completed.is_(True))
        .scalar(),
        "focus_sessions": db.query(func.count(FocusRecord.id))
        .filter(FocusRecord.user_id == user_id, FocusRecord.duration_minutes > 0)
        .scalar(),
        "focus_minutes": sum(by_day.values()),
        "max_day_minutes": max(by_day.values(), default=0),
        "early_sessions": sum(1 for (started,) in early if 4 <= started.hour < 8),
        "longest_streak": streak_info(db, user_id)["longest"],
        "goal_days": int(goal_days or 0),
        "plans_created": db.query(func.count(StudyPlan.id)).filter(StudyPlan.user_id == user_id).scalar(),
        "ai_plans": db.query(func.count(StudyPlan.id))
        .filter(StudyPlan.user_id == user_id, StudyPlan.source == "ai")
        .scalar(),
        "imports": db.query(func.count(ImportLog.id))
        .filter(ImportLog.user_id == user_id, ImportLog.success_count > 0)
        .scalar(),
    }


def evaluate_achievements(db: Session, user_id: int) -> List[dict]:
    """检查并解锁新成就，返回本次新解锁的成就（附带 XP 奖励）。"""
    unlocked = {code for (code,) in db.query(UserAchievement.code).filter_by(user_id=user_id).all()}
    pending = [item for item in ACHIEVEMENTS if item.code not in unlocked]
    if not pending:
        return []
    metrics = _metrics(db, user_id)
    fresh = []
    for item in pending:
        if metrics.get(item.metric, 0) >= item.target:
            db.add(UserAchievement(user_id=user_id, code=item.code, unlocked_at=timeutil.now()))
            award(db, user_id, item.xp, "achievement", item.code)
            fresh.append(achievement_dict(item, True, metrics))
    db.flush()
    return fresh


def achievement_dict(item: Achievement, unlocked: bool, metrics: Dict[str, int], unlocked_at=None) -> dict:
    value = int(metrics.get(item.metric, 0))
    return {
        "code": item.code,
        "title": item.title,
        "description": item.description,
        "icon": item.icon,
        "xp": item.xp,
        "unlocked": unlocked,
        "unlocked_at": unlocked_at.isoformat() if unlocked_at else None,
        "value": min(value, item.target),
        "target": item.target,
        "progress": 100 if unlocked else min(99, round(value / item.target * 100)),
    }


def achievements_view(db: Session, user_id: int) -> List[dict]:
    rows = {code: at for code, at in db.query(UserAchievement.code, UserAchievement.unlocked_at).filter_by(user_id=user_id)}
    metrics = _metrics(db, user_id)
    return [achievement_dict(item, item.code in rows, metrics, rows.get(item.code)) for item in ACHIEVEMENTS]


# ---------------------------------------------------------------- 奖励回执
class RewardTracker:
    """
    在一次用户动作前后对比，生成前端庆祝动画所需的回执：
    获得多少 XP、是否升级、新成就、连续天数、每日目标是否刚刚达成。
    """

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.xp_before = total_xp(db, user.id)
        self.level_before = level_info(self.xp_before)["level"]
        self.goal_reached_before = daily_goal_info(db, user)["reached"]

    def finish(self) -> dict:
        freeze = settle_freezes(self.db, self.user)
        new_achievements = evaluate_achievements(self.db, self.user.id)
        xp_after = total_xp(self.db, self.user.id)
        level = level_info(xp_after)
        goal = daily_goal_info(self.db, self.user)
        return {
            "xp_gained": xp_after - self.xp_before,
            "level": level,
            "level_up": level["level"] > self.level_before,
            "streak": streak_info(self.db, self.user.id),
            "daily_goal": goal,
            "goal_just_reached": goal["reached"] and not self.goal_reached_before,
            "new_achievements": new_achievements,
            # 本次动作触发的保护卡变化：{used: [日期], earned: [日期]}
            "streak_freeze": freeze,
        }


def maybe_award_daily_goal(db: Session, user: User, day: Optional[date] = None) -> int:
    day = day or timeutil.today()
    if daily_goal_info(db, user, day)["reached"]:
        return award(db, user.id, XP_DAILY_GOAL, "daily_goal", day.isoformat(), on=day)
    return 0


# ---------------------------------------------------------------- 排行榜 / 热力图 / 科目分布
def weekly_leaderboard(db: Session, me: User, limit: int = 10, ref: Optional[date] = None) -> dict:
    week_start = timeutil.monday_of(ref or timeutil.today())
    rows = (
        db.query(User.id, User.full_name, User.username, User.avatar, User.is_demo, func.sum(XpEvent.amount))
        .join(XpEvent, XpEvent.user_id == User.id)
        .filter(XpEvent.event_date >= week_start, User.is_active.is_(True))
        .filter((User.is_demo.is_(False)) | (User.id == me.id) if not me.is_demo else True)
        .group_by(User.id)
        .order_by(func.sum(XpEvent.amount).desc(), User.id.asc())
        .all()
    )
    entries = [
        {
            "rank": index,
            "user_id": uid,
            "name": full_name or username,
            "avatar": avatar or "🦉",
            "xp": int(xp or 0),
            "is_me": uid == me.id,
            "is_demo": bool(is_demo) and uid != me.id,
        }
        for index, (uid, full_name, username, avatar, is_demo, xp) in enumerate(rows, start=1)
    ]
    mine = next((entry for entry in entries if entry["is_me"]), None)
    if mine is None:
        mine = {
            "rank": len(entries) + 1,
            "user_id": me.id,
            "name": me.full_name or me.username,
            "avatar": me.avatar or "🦉",
            "xp": 0,
            "is_me": True,
            "is_demo": False,
        }
    return {"week_start": week_start.isoformat(), "entries": entries[:limit], "me": mine, "total": len(entries)}


def group_leaderboard(db: Session, me: User, member_ids: List[int], ref: Optional[date] = None) -> dict:
    """小组内本周 XP 排行：与全站周榜同一口径（本周一起的 XP 流水），没有 XP 的成员也列出（0 分垫底）。"""
    week_start = timeutil.monday_of(ref or timeutil.today())
    if not member_ids:
        return {"week_start": week_start.isoformat(), "entries": [], "me": None, "total": 0}
    xp = dict(
        db.query(XpEvent.user_id, func.sum(XpEvent.amount))
        .filter(XpEvent.user_id.in_(member_ids), XpEvent.event_date >= week_start)
        .group_by(XpEvent.user_id)
        .all()
    )
    users = db.query(User).filter(User.id.in_(member_ids)).all()
    users.sort(key=lambda u: (-int(xp.get(u.id) or 0), u.id))
    entries = [
        {
            "rank": index,
            "user_id": u.id,
            "name": u.full_name or u.username,
            "avatar": u.avatar or "🦉",
            "xp": int(xp.get(u.id) or 0),
            "is_me": u.id == me.id,
            "is_demo": False,
        }
        for index, u in enumerate(users, start=1)
    ]
    mine = next((entry for entry in entries if entry["is_me"]), None)
    return {"week_start": week_start.isoformat(), "entries": entries, "me": mine, "total": len(entries)}


def heatmap(db: Session, user_id: int, weeks: int = 16, ref: Optional[date] = None) -> dict:
    ref = ref or timeutil.today()
    start = timeutil.monday_of(ref) - timedelta(weeks=weeks - 1)
    minutes = focus_minutes_by_day(db, user_id, since=start)
    tasks = completed_tasks_by_day(db, user_id, since=start)

    def level(m: int, t: int) -> int:
        if m >= 120:
            return 4
        if m >= 60:
            return 3
        if m >= 30:
            return 2
        return 1 if (m > 0 or t > 0) else 0

    days = []
    cursor = start
    while cursor <= ref:
        key = cursor.isoformat()
        m, t = minutes.get(key, 0), tasks.get(key, 0)
        days.append({"date": key, "minutes": m, "tasks": t, "level": level(m, t)})
        cursor += timedelta(days=1)
    return {"start": start.isoformat(), "end": ref.isoformat(), "weeks": weeks, "days": days}


def subject_breakdown(db: Session, user_id: int, days: int = 30, ref: Optional[date] = None) -> List[dict]:
    ref = ref or timeutil.today()
    since = (ref - timedelta(days=days - 1)).isoformat()
    rows = (
        db.query(func.coalesce(FocusRecord.subject, "自由专注"), func.sum(FocusRecord.duration_minutes))
        .filter(FocusRecord.user_id == user_id, FocusRecord.record_date >= since)
        .group_by(func.coalesce(FocusRecord.subject, "自由专注"))
        .order_by(func.sum(FocusRecord.duration_minutes).desc())
        .all()
    )
    items = [{"subject": subject or "自由专注", "minutes": int(total or 0)} for subject, total in rows if total]
    if len(items) > 6:
        rest = sum(item["minutes"] for item in items[5:])
        items = items[:5] + [{"subject": "其他", "minutes": rest}]
    return items


def subject_stats(db: Session, user_id: int, days: int = 30, ref: Optional[date] = None, top: int = 8) -> dict:
    """按科目统计专注分钟与占比（科目为空记作"自由专注"，超过 top 个时其余合并为"其他"）。"""
    ref = ref or timeutil.today()
    since = ref - timedelta(days=days - 1)
    label = func.coalesce(func.nullif(FocusRecord.subject, ""), "自由专注")
    rows = (
        db.query(label, func.sum(FocusRecord.duration_minutes), func.count(FocusRecord.id))
        .filter(FocusRecord.user_id == user_id, FocusRecord.record_date >= since.isoformat(),
                FocusRecord.record_date <= ref.isoformat())
        .group_by(label)
        .order_by(func.sum(FocusRecord.duration_minutes).desc())
        .all()
    )
    items = [{"subject": s, "minutes": int(m or 0), "sessions": int(c or 0)} for s, m, c in rows if m]
    if len(items) > top:
        rest = items[top - 1:]
        items = items[: top - 1] + [{"subject": "其他", "minutes": sum(i["minutes"] for i in rest),
                                      "sessions": sum(i["sessions"] for i in rest)}]
    total = sum(item["minutes"] for item in items)
    for item in items:
        item["percent"] = round(item["minutes"] / total * 100, 1) if total else 0
    return {"days": days, "start": since.isoformat(), "end": ref.isoformat(), "total_minutes": total, "items": items}
