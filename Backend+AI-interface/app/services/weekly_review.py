# -*- coding: utf-8 -*-
"""
每周 AI 复盘：统计某一周（周一开始）的学习数据，交给当前用户的模型写复盘与下周建议；
没有可用模型（或模型调用失败）时用规则生成。结果缓存在 WeeklyReport(kind="ai")。

统计口径：
  · 计划完成率：截止日在本周的任务中，到周末（或今天）为止已完成的比例；本周没有任务时为 None
  · 完成任务：completed_at 落在本周的任务数
  · 逾期任务：截止日在本周、且"至今未完成并已过截止日"或"完成时间晚于截止日"的任务数
  · 拖延最多的科目：按逾期任务数排序，最多 3 个
  · 连续天数：周一前一天的连续天数 → 周日（本周则为今天）的连续天数
"""

import json
from collections import Counter
from datetime import date, timedelta
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai import llm, providers
from app.ai.llm import LlmError
from app.core import timeutil
from app.core.errors import ApiError
from app.models import FocusRecord, StudyTask, User, WeeklyReport
from app.services import gamification
from app.services.tasks import visible_tasks

KIND = "ai"
MAX_SUGGESTIONS = 6
MIN_SUGGESTIONS = 3

SYSTEM_PROMPT = """你是一名温和、务实的大学学习教练。用户会给你他某一周的学习统计（JSON）。
请写一份简短的中文周复盘和下周建议，只输出一个 JSON 对象，不要输出其它文字：
{"review_markdown": "Markdown 格式的复盘，2-4 段或要点，150-300 字", "suggestions": ["建议1", "建议2", "建议3"]}
要求：
1. 复盘基于数据说话：先肯定做得好的地方，再指出问题（如完成率低、某科目拖延、专注天数少），与上周对比时写出具体数字。
2. suggestions 给 3-6 条下周可执行的建议，每条一句话（不超过 50 字），具体到科目、时段或数量，不要空话。
3. 数据很少（几乎没学习）时，不要批评，鼓励从每天一个小目标开始。
4. 不要编造统计里没有的数据。"""


# ---------------------------------------------------------------- 周范围
def resolve_week(week_start: Optional[str]) -> Tuple[date, date]:
    """返回 (周一, 周日)。不传时取上一完整周；传入任意日期会对齐到所在周的周一。"""
    today = timeutil.today()
    if week_start:
        parsed = timeutil.parse_date(week_start)
        if parsed is None:
            raise ApiError(422, "week_start 格式应为 YYYY-MM-DD")
        start = timeutil.monday_of(parsed)
    else:
        start = timeutil.monday_of(today) - timedelta(days=7)
    if start > today:
        raise ApiError(422, "还没到这一周，无法复盘")
    return start, start + timedelta(days=6)


# ---------------------------------------------------------------- 统计
def _focus_rows(db: Session, user_id: int, start: date, end: date):
    return (
        db.query(FocusRecord.record_date, FocusRecord.subject, FocusRecord.duration_minutes)
        .filter(FocusRecord.user_id == user_id, FocusRecord.record_date >= start.isoformat(),
                FocusRecord.record_date <= end.isoformat())
        .all()
    )


def _tasks_done(db: Session, user_id: int, start: date, end: date) -> int:
    return (
        db.query(StudyTask.id)
        .filter(StudyTask.user_id == user_id, StudyTask.completed.is_(True),
                StudyTask.completed_at >= timeutil.combine(start, "00:00"),
                StudyTask.completed_at < timeutil.combine(end + timedelta(days=1), "00:00"))
        .count()
    )


def _focus_minutes(db: Session, user_id: int, start: date, end: date) -> int:
    return sum(int(minutes or 0) for _, _, minutes in _focus_rows(db, user_id, start, end))


def compute_stats(db: Session, user: User, start: date, end: date) -> dict:
    today = timeutil.today()
    cutoff = min(end, today)

    # 专注：总分钟、科目分布、专注天数
    by_subject: Counter = Counter()
    days = set()
    for record_date, subject, minutes in _focus_rows(db, user.id, start, end):
        minutes = int(minutes or 0)
        if minutes <= 0:
            continue
        by_subject[(subject or "").strip() or "自由专注"] += minutes
        days.add(record_date)
    focus_minutes = sum(by_subject.values())

    # 计划：截止日在本周的任务
    planned = visible_tasks(
        db.query(StudyTask.subject, StudyTask.due_date, StudyTask.completed, StudyTask.completed_at)
        .filter(StudyTask.user_id == user.id, StudyTask.due_date >= start.isoformat(),
                StudyTask.due_date <= end.isoformat())
    ).all()
    finished, overdue = 0, Counter()
    overdue_count = 0
    for subject, due, completed, completed_at in planned:
        done_date = completed_at.date() if completed and completed_at else None
        if completed and (done_date is None or done_date <= cutoff):
            finished += 1
        late = (not completed and due < today.isoformat()) or (done_date is not None and done_date.isoformat() > due)
        if late:
            overdue_count += 1
            overdue[(subject or "").strip() or "未分类"] += 1

    tasks_done = _tasks_done(db, user.id, start, end)
    prev_start, prev_end = start - timedelta(days=7), start - timedelta(days=1)
    return {
        "plan_completion_rate": round(finished / len(planned) * 100) if planned else None,
        "tasks_planned": len(planned),
        "tasks_done": tasks_done,
        "tasks_overdue": overdue_count,
        "focus_minutes": focus_minutes,
        "focus_days": len(days),
        "streak_start": gamification.streak_info(db, user.id, ref=start - timedelta(days=1))["current"],
        "streak_end": gamification.streak_info(db, user.id, ref=cutoff)["current"],
        "top_procrastinated": [name for name, _ in overdue.most_common(3)],
        "subjects": [{"subject": name, "minutes": minutes} for name, minutes in by_subject.most_common()],
        "compare": {
            "focus_minutes_delta": focus_minutes - _focus_minutes(db, user.id, prev_start, prev_end),
            "tasks_done_delta": tasks_done - _tasks_done(db, user.id, prev_start, prev_end),
        },
    }


# ---------------------------------------------------------------- 规则复盘
def _hm(minutes: int) -> str:
    minutes = int(minutes)
    hours, rest = divmod(abs(minutes), 60)
    text = f"{hours} 小时 {rest} 分钟" if hours else f"{rest} 分钟"
    return text


def rule_review(stats: dict, user: User) -> Tuple[str, List[str]]:
    focus, days = stats["focus_minutes"], stats["focus_days"]
    rate = stats["plan_completion_rate"]
    delta = stats["compare"]["focus_minutes_delta"]
    lines = ["### 本周概览"]
    if focus == 0 and stats["tasks_done"] == 0:
        lines.append("- 这一周还没有专注或完成任务的记录，没关系，下周从一个小目标重新开始。")
    else:
        lines.append(f"- 专注 **{_hm(focus)}**，共 {days} 天有专注记录，完成任务 {stats['tasks_done']} 个。")
        if rate is not None:
            lines.append(f"- 本周计划 {stats['tasks_planned']} 个任务，完成率 **{rate}%**，逾期 {stats['tasks_overdue']} 个。")
        if delta:
            word = "多" if delta > 0 else "少"
            lines.append(f"- 比上周{word}专注了 {_hm(abs(delta))}。")
        if stats["subjects"]:
            top = stats["subjects"][0]
            lines.append(f"- 投入最多的科目是「{top['subject']}」（{_hm(top['minutes'])}）。")
    lines.append(f"- 连续学习：{stats['streak_start']} 天 → {stats['streak_end']} 天。")

    suggestions: List[str] = []
    goal = int(user.daily_goal_minutes or 60)
    if days < 5:
        suggestions.append(f"争取下周至少 5 天有专注记录，哪怕每天只完成一个 25 分钟的番茄。")
    if rate is not None and rate < 70:
        suggestions.append("计划完成率偏低：下周每天只排 2-3 个最重要的任务，做完再加。")
    if stats["top_procrastinated"]:
        names = "、".join(stats["top_procrastinated"][:2])
        suggestions.append(f"「{names}」逾期最多，下周把它们放到精力最好的时段优先完成。")
    if focus and days and focus / days < goal:
        suggestions.append(f"平均每个学习日专注 {round(focus / days)} 分钟，低于每日目标 {goal} 分钟，可以多安排一个番茄。")
    if len(stats["subjects"]) >= 2:
        least = stats["subjects"][-1]
        suggestions.append(f"「{least['subject']}」投入较少（{_hm(least['minutes'])}），下周给它固定一个时段。")
    if stats["streak_end"] >= 3:
        suggestions.append(f"已连续学习 {stats['streak_end']} 天，保持每天打卡，别让火苗断掉。")
    fallback = [
        "每周日晚上花 10 分钟回顾本周、排好下周计划。",
        "完成一个任务后立刻勾选，及时的反馈能让你更有动力。",
        "考试前两周开始安排真题与错题回顾，不要临时抱佛脚。",
    ]
    for item in fallback:
        if len(suggestions) >= MIN_SUGGESTIONS:
            break
        suggestions.append(item)
    return "\n".join(lines), suggestions[:MAX_SUGGESTIONS]


# ---------------------------------------------------------------- 模型复盘
def llm_review(config, stats: dict, start: date, end: date, user: User) -> Tuple[str, List[str]]:
    payload = {
        "week": f"{start.isoformat()} ~ {end.isoformat()}",
        "daily_goal_minutes": int(user.daily_goal_minutes or 60),
        "plan_completion_rate_percent": stats["plan_completion_rate"],
        "tasks_planned": stats["tasks_planned"],
        "tasks_done": stats["tasks_done"],
        "tasks_overdue": stats["tasks_overdue"],
        "focus_minutes": stats["focus_minutes"],
        "focus_days": stats["focus_days"],
        "streak_days_before_week": stats["streak_start"],
        "streak_days_at_week_end": stats["streak_end"],
        "most_procrastinated_subjects": stats["top_procrastinated"],
        "focus_minutes_by_subject": stats["subjects"][:10],
        "vs_last_week": stats["compare"],
    }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "我这一周的学习统计：\n" + json.dumps(payload, ensure_ascii=False)},
    ]
    data = llm.chat_json(config, messages, temperature=0.5)
    review = str(data.get("review_markdown") or data.get("review") or "").strip()
    raw = data.get("suggestions")
    suggestions = [str(item).strip()[:120] for item in raw if str(item).strip()] if isinstance(raw, list) else []
    if not review or not suggestions:
        raise LlmError("模型返回的复盘内容不完整")
    return review[:3000], suggestions[:MAX_SUGGESTIONS]


# ---------------------------------------------------------------- 入口
def _cached(db: Session, user: User, start: date) -> Optional[WeeklyReport]:
    return (
        db.query(WeeklyReport)
        .filter(WeeklyReport.user_id == user.id, WeeklyReport.week_start == start.isoformat(),
                WeeklyReport.kind == KIND)
        .first()
    )


def weekly_review(db: Session, user: User, week_start: Optional[str] = None, refresh: bool = False) -> dict:
    start, end = resolve_week(week_start)
    row = _cached(db, user, start)
    if row is not None and not refresh:
        try:
            return {**json.loads(row.content), "cached": True}
        except ValueError:
            pass  # 缓存损坏则重新生成

    stats = compute_stats(db, user, start, end)
    config = providers.resolve(db, user)
    provider, model, error = "rule", None, None
    if config is not None:
        try:
            review, suggestions = llm_review(config, stats, start, end, user)
            provider, model = "llm", f"{config.name} · {config.model}"
        except LlmError as exc:
            error = exc.message
    if provider == "rule":
        review, suggestions = rule_review(stats, user)

    result = {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "stats": stats,
        "review_markdown": review,
        "suggestions": suggestions,
        "provider": provider,
        "model": model,
        "generated_at": timeutil.now().isoformat(),
        # 本周尚未结束时数据还会变化，前端可提示"可刷新"
        "in_progress": end >= timeutil.today(),
    }
    if error:
        result["fallback_reason"] = f"模型调用失败，已用规则生成：{error}"

    content = json.dumps(result, ensure_ascii=False)
    if row is None:
        db.add(WeeklyReport(user_id=user.id, week_start=start.isoformat(), kind=KIND, content=content))
    else:
        row.content = content
        row.created_at = timeutil.now()
    try:
        db.commit()
    except IntegrityError:  # 并发生成同一周：以先写入的为准，本次结果照常返回
        db.rollback()
    return {**result, "cached": False}
