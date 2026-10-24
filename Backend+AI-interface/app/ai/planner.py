# -*- coding: utf-8 -*-
"""
学习计划生成器。

流程：解析需求 -> 读取课表与已定时任务 -> 计算每天的空闲时段 -> 生成回复。

每次回复固定分为两部分，无论背后是规则引擎还是任意 OpenAI 兼容模型：
  1. advice —— 写给学生的学习建议（Markdown 文本）
  2. plan   —— 结构化计划：tasks（带日期时刻的学习块）+ courses（需求里提到的新课程），可一键导入

大模型给出的每个学习块都必须落在真实空闲时段内、每门课程必须字段完整才会被采纳；
全部无效或调用失败时自动回退规则引擎，并在 fallback_reason 里说明原因。

generate_draft 只返回草稿，不落库；用户点"采纳计划"后才调用 commit_draft。
"""

import json
import logging
import re
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.ai import llm, providers
from app.ai.nlu import parse_request
from app.core import timeutil
from app.core.errors import ApiError
from app.models import StudyPlan, StudyTask, User
from app.services import prefs as prefs_service
from app.services import schedule
from app.services.tasks import apply_schedule, visible_tasks

logger = logging.getLogger("study_planner.ai")

# 可排程窗口：避开午饭 12:00-13:30、晚饭 17:30-18:30，22:00 后不安排
WINDOWS = {
    "morning": ("08:00", "12:00"),
    "afternoon": ("13:30", "17:30"),
    "evening": ("18:30", "22:00"),
}
MIN_SLOT = 30
COURSE_BUFFER = 10
MAX_DAYS = 31
HISTORY_TURNS = 20  # 最近 10 轮（用户 + 助手各 10 条）

PHASES_REGULAR = ["梳理知识框架", "专项练习", "错题复盘", "预习新内容"]
PHASES_EXAM = ["梳理考点", "真题训练", "错题复盘", "限时模拟"]


# ---------------------------------------------------------------- 空闲时段
def free_slots(busy: List[tuple], day: date, prefer: Optional[str] = None, pref: Optional[dict] = None) -> List[dict]:
    """在三个可排程窗口里扣掉课程与已有任务；pref 为学习时段偏好（最早/最晚时间、避开时段、优先顺序）。"""
    pref = pref or {}
    intervals = []
    for start_hm, end_hm in busy:
        intervals.append((timeutil.hm_to_minutes(start_hm) - COURSE_BUFFER, timeutil.hm_to_minutes(end_hm) + COURSE_BUFFER))
    intervals.sort()

    floor = 0
    if day == timeutil.today():
        current = timeutil.now()
        floor = ((current.hour * 60 + current.minute + 4) // 5) * 5 + 5

    slots = []
    earliest = timeutil.hm_to_minutes(pref.get("earliest") or "00:00")
    latest = timeutil.hm_to_minutes(pref.get("latest") or "23:59")
    avoid = set(pref.get("avoid") or []) - {prefer}
    for segment, (start_hm, end_hm) in WINDOWS.items():
        if segment in avoid:
            continue
        cursor = max(timeutil.hm_to_minutes(start_hm), floor, earliest)
        window_end = min(timeutil.hm_to_minutes(end_hm), latest)
        for busy_start, busy_end in intervals:
            if busy_end <= cursor or busy_start >= window_end:
                continue
            if busy_start - cursor >= MIN_SLOT:
                slots.append((cursor, busy_start, segment))
            cursor = max(cursor, busy_end)
        if window_end - cursor >= MIN_SLOT:
            slots.append((cursor, window_end, segment))

    # 本次明确说了时段 > 设置里的偏好 / 专注习惯 > 时间先后
    ranking = ([prefer] if prefer else []) + [seg for seg in (pref.get("segments") or []) if seg != prefer]
    if ranking:
        slots.sort(key=lambda s: (ranking.index(s[2]) if s[2] in ranking else len(ranking), s[0]))
    return [
        {"start": timeutil.minutes_to_hm(s), "end": timeutil.minutes_to_hm(e), "minutes": e - s, "segment": seg}
        for s, e, seg in slots
    ]


def day_contexts(db: Session, user: User, start: date, days: int, prefer: Optional[str] = None,
                 pref: Optional[dict] = None) -> List[dict]:
    courses = schedule.user_courses(db, user)
    timed = visible_tasks(
        db.query(StudyTask)
        .filter(
            StudyTask.user_id == user.id,
            StudyTask.start_time.isnot(None),
            StudyTask.completed.is_(False),
            StudyTask.due_date >= start.isoformat(),
            StudyTask.due_date <= (start + timedelta(days=days - 1)).isoformat(),
        )
    ).all()
    contexts = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        day_courses = schedule.courses_on_date(db, user, day, courses)
        day_tasks = [t for t in timed if t.due_date == day.isoformat()]
        busy = [(c.start_time, c.end_time) for c in day_courses]
        busy += [(t.start_time.strftime("%H:%M"), t.end_time.strftime("%H:%M")) for t in day_tasks if t.end_time]
        contexts.append(
            {
                "date": day,
                "courses": [{"name": c.course_name, "start": c.start_time, "end": c.end_time} for c in day_courses],
                "task_count": len(day_tasks),
                "free": free_slots(busy, day, prefer, pref),
            }
        )
    return contexts


# ---------------------------------------------------------------- 规则排程
def _rule_tasks(contexts: List[dict], subjects: List[str], daily_minutes: int, intensity: float, exam: bool,
                variant: int, block: Optional[int] = None, rest: int = 10) -> List[dict]:
    phases = PHASES_EXAM if exam else PHASES_REGULAR
    if block:
        session = max(20, round(block * (0.7 if intensity < 1 else 1.15 if intensity > 1 else 1)))
    else:
        session = 25 if intensity < 1 else (50 if intensity > 1 else 45)
    tasks: List[dict] = []
    subject_index = variant
    phase_counter: Dict[str, int] = {}
    total_days = len(contexts)

    for day_index, ctx in enumerate(contexts):
        budget = daily_minutes
        slots = list(ctx["free"])
        if variant % 2 == 1:
            # "换一版"时优先用靠后的时段，给出明显不同的安排
            slots.sort(key=lambda s: -timeutil.hm_to_minutes(s["start"]))
        for slot in slots:
            cursor = timeutil.hm_to_minutes(slot["start"])
            slot_end = timeutil.hm_to_minutes(slot["end"])
            while budget >= 20 and slot_end - cursor >= 20:
                length = min(session, budget, slot_end - cursor)
                if length < 20:
                    break
                subject = subjects[subject_index % len(subjects)]
                subject_index += 1
                count = phase_counter.get(subject, 0)
                phase_counter[subject] = count + 1
                phase = phases[count % len(phases)]
                near_exam = exam and day_index >= total_days - 2
                tasks.append(
                    {
                        "date": ctx["date"].isoformat(),
                        "start_time": timeutil.minutes_to_hm(cursor),
                        "duration_minutes": length,
                        "title": f"{subject}：{phase}",
                        "subject": subject,
                        "priority": 3 if near_exam else 2,
                        "note": f"建议 {max(1, length // 25)} 个番茄，结束后休息 {rest} 分钟",
                    }
                )
                budget -= length
                cursor += length + rest
            if budget < 20:
                break
    return sorted(tasks, key=lambda t: (t["date"], t["start_time"]))


# ---------------------------------------------------------------- 大模型（OpenAI 兼容）
SYSTEM_PROMPT = """你是大学生学习规划助手。根据用户需求与给定上下文，输出一个 JSON 对象，不要输出任何其他文字。
JSON 结构：
{
  "advice": "写给学生的学习建议，Markdown，3-6 条，针对其科目与时间安排，不要复述日程表",
  "title": "计划标题，不超过 20 字",
  "tasks": [{"date": "YYYY-MM-DD", "start_time": "HH:MM", "duration_minutes": 45,
             "title": "科目：具体内容", "subject": "科目", "priority": 2, "note": "一句执行提示"}],
  "courses": [{"course_name": "课程名", "day_of_week": 1, "start_period": 1, "end_period": 2,
               "weeks": [1, 2, 3], "teacher": "", "classroom": ""}]
}
规则：
- 必须覆盖 context.days 里的每一天：只要某天 free_slots 合计不少于 30 分钟，就要给这一天安排学习块，不能只排前一两天。
- tasks 只能安排在 context.days[].free_slots 内：start_time 不早于时段开始，start_time+duration_minutes 不晚于时段结束。
- free_slots 已按学生的时段偏好排序（越靠前越优先），constraints.study_prefs 是学生在设置里的偏好或专注习惯，请尽量遵守。
- constraints.memory 是之前几轮对话确定下来的要点（科目、日期范围、每日时长、偏好、补充要求），本轮没有改动的部分必须沿用，不要遗忘。
- 每个学习块 20-120 分钟，每天合计不超过 constraints.daily_minutes；priority 取 0-3（3 最高）。
- 用户明确说了新课程（如：我周三下午还有一门选修课）时才填写 courses，day_of_week 1=周一，节次参照 period_times；否则 courses 返回 []。
- 所有文字用简体中文。"""


def _llm_messages(parsed: dict, contexts: List[dict], minutes: int, user: User, db: Session,
                  history: List[dict], variant: int, memory: Optional[dict] = None,
                  pref: Optional[dict] = None) -> List[dict]:
    context = {
        "today": timeutil.today().isoformat(),
        "teaching_week": schedule.teaching_week(user),
        "period_times": [f"{i + 1}:{p['start']}-{p['end']}" for i, p in enumerate(schedule.period_times(user))],
        "known_subjects": list(dict.fromkeys(c.course_name for c in schedule.user_courses(db, user)))[:20],
        "days": [
            {
                "date": c["date"].isoformat(),
                "weekday": timeutil.weekday_label(c["date"]),
                "courses": [f"{x['start']}-{x['end']} {x['name']}" for x in c["courses"]],
                "free_slots": [f"{s['start']}-{s['end']}" for s in c["free"]],
            }
            for c in contexts
        ],
    }
    constraints = {
        "daily_minutes": minutes,
        "subjects": parsed["subjects"],
        "exam_mode": parsed["exam"],
        "prefer": parsed.get("prefer"),
        "variant": variant,
        "date_range": [contexts[0]["date"].isoformat(), contexts[-1]["date"].isoformat()] if contexts else [],
        "study_prefs": prefs_service.describe(pref) if pref else "",
        "memory": memory or {},
    }
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # 最近 10 轮完整对话：助手回合由前端附带上一版计划摘要，模型才能在追问时"记得"自己排过什么
    for turn in history[-HISTORY_TURNS:]:
        messages.append({"role": turn["role"], "content": str(turn["content"])[:1500]})
    messages.append({
        "role": "user",
        "content": f"需求：{parsed['raw']}\n约束：{json.dumps(constraints, ensure_ascii=False)}\n"
                   f"上下文：{json.dumps(context, ensure_ascii=False)}",
    })
    return messages


def _validate_ai_tasks(tasks, contexts: List[dict], daily_minutes: int) -> Optional[List[dict]]:
    by_date = {c["date"].isoformat(): c["free"] for c in contexts}
    used: Dict[str, int] = {}
    valid = []
    for item in tasks if isinstance(tasks, list) else []:
        try:
            day = str(item["date"])
            start = timeutil.hm_to_minutes(str(item["start_time"]))
            length = int(item["duration_minutes"])
            title = str(item["title"]).strip()[:120]
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if day not in by_date or not title or not 20 <= length <= 120:
            continue
        inside = any(
            timeutil.hm_to_minutes(s["start"]) <= start and start + length <= timeutil.hm_to_minutes(s["end"])
            for s in by_date[day]
        )
        if not inside or used.get(day, 0) + length > daily_minutes + 15:
            continue
        used[day] = used.get(day, 0) + length
        try:
            priority = max(0, min(3, int(item.get("priority") or 2)))
        except (TypeError, ValueError):
            priority = 2
        valid.append({
            "date": day,
            "start_time": timeutil.minutes_to_hm(start),
            "duration_minutes": length,
            "title": title,
            "subject": str(item.get("subject") or "")[:80],
            "priority": priority,
            "note": str(item.get("note") or "")[:200],
        })
    return sorted(valid, key=lambda t: (t["date"], t["start_time"])) or None


def _validate_ai_courses(courses, user: User) -> Tuple[List[dict], int]:
    total = int(user.total_weeks or 20)
    periods = len(schedule.period_times(user))
    valid, dropped = [], 0
    for item in courses if isinstance(courses, list) else []:
        try:
            name = str(item["course_name"]).strip()[:160]
            day = int(item["day_of_week"])
            p1, p2 = int(item["start_period"]), int(item["end_period"])
            raw_weeks = item.get("weeks") or list(range(1, total + 1))
            weeks = sorted({int(w) for w in raw_weeks if 1 <= int(w) <= total})
        except (KeyError, TypeError, ValueError, AttributeError):
            dropped += 1
            continue
        if not name or not 1 <= day <= 7 or not 1 <= p1 <= p2 <= periods or not weeks:
            dropped += 1
            continue
        start, end = schedule.periods_to_times(user, p1, p2)
        valid.append({
            "course_name": name, "day_of_week": day, "start_period": p1, "end_period": p2, "weeks": weeks,
            "week_text": schedule.format_weeks(weeks), "start_time": start, "end_time": end,
            "teacher": str(item.get("teacher") or "")[:120], "classroom": str(item.get("classroom") or "")[:80],
            "color": schedule.color_for(name),
        })
    return valid, dropped


# ---------------------------------------------------------------- 规则引擎的建议
def _rule_advice(parsed: dict, minutes: int, total_days: int, tasks: List[dict], short_days: int) -> str:
    subjects = "、".join(parsed["subjects"])
    lines = [f"**{subjects}**：{total_days} 天里安排了 {len(tasks)} 个学习块，每天约 {minutes} 分钟。"]
    if parsed["exam"]:
        lines += [
            "- 先花 1-2 个学习块把考点清单列出来，再按「真题 → 错题 → 限时模拟」推进",
            "- 考前两天以回顾错题和公式为主，不再开新题型",
        ]
    else:
        lines += [
            "- 每个学习块开头先用 5 分钟回顾上次内容，结束前写 3 行要点，记忆更牢",
            "- 当天课程当天复习，效果比集中到周末突击好得多",
        ]
    if minutes >= 180:
        lines.append("- 每天超过 3 小时，注意每两个番茄后起身活动，别连续久坐")
    elif minutes <= 45:
        lines.append("- 时间较少，优先做最薄弱的一章，宁可少而精")
    if short_days:
        lines.append(f"- 有 {short_days} 天课程较满、空闲不足，已按实际可用时间缩减，可以在周末补上")
    if parsed.get("from_timetable"):
        lines.append("- 你没有指定科目，我按本周课表里的课程安排了复习，可以直接告诉我想换的科目")
    lines.append("- 点击任务旁的 ▶ 开始番茄钟，专注时长会记到任务上并获得 XP")
    return "\n".join(lines)


# ---------------------------------------------------------------- 对外入口
def _title(parsed: dict, days: int) -> str:
    subjects = parsed["subjects"]
    head = "、".join(subjects[:2]) if subjects and not parsed.get("from_timetable") else ""
    if parsed["exam"]:
        return f"{head}备考冲刺" if head else "期末备考计划"
    if days == 1:
        label = "今晚" if parsed.get("prefer") == "evening" and parsed["start"] == timeutil.today() else "单日"
        return f"{head}{label}学习安排" if head else f"{label}学习安排"
    return f"{head}{days}天学习计划" if head else f"{days}天学习计划"


def _merge_memory(parsed: dict, memory: Optional[dict], ref: date) -> None:
    """
    多轮对话：本轮明确提到的字段覆盖上一轮，没提到的沿用记忆。
    例："改到 11.1-11.10" 只换日期，科目和每天时长不变；"加上英语" 在原科目上追加。
    """
    if not memory:
        return
    remembered = [s for s in memory.get("subjects") or [] if s]
    if parsed["subjects"] and remembered and re.search(r"加上|再加|也要|还有|顺便", parsed["raw"]):
        parsed["subjects"] = list(dict.fromkeys(remembered + parsed["subjects"]))[:5]
    elif not parsed["subjects"] and remembered:
        parsed["subjects"] = remembered[:5]
        parsed["from_memory"] = True
    mem_start = timeutil.parse_date(memory.get("start_date"), None)
    if not parsed["date_explicit"] and mem_start:
        parsed["start"] = mem_start
        if not parsed["duration_only"]:
            parsed["days"] = memory.get("days") or parsed["days"]
    parsed["days"] = parsed["days"] or memory.get("days")
    if parsed["daily_minutes"] is None and memory.get("daily_minutes"):
        parsed["daily_minutes"] = int(memory["daily_minutes"])
        parsed["minutes_from_memory"] = True
    if not parsed["prefer"] and not re.search(r"不限|全天|任意时段|都可以", parsed["raw"]):
        parsed["prefer"] = memory.get("prefer")
    parsed["exam"] = parsed["exam"] or bool(memory.get("exam"))


def _memory_out(parsed: dict, start: date, total_days: int, minutes: int, memory: Optional[dict]) -> dict:
    notes = list((memory or {}).get("notes") or [])
    raw = parsed["raw"].strip()
    if raw and raw not in notes:
        notes.append(raw[:80])
    return {
        "subjects": parsed["subjects"][:8],
        "start_date": start.isoformat(),
        "days": total_days,
        "daily_minutes": minutes,
        "prefer": parsed.get("prefer"),
        "exam": bool(parsed["exam"]),
        "notes": notes[-10:],
    }


def generate_draft(db: Session, user: User, message: str, days: Optional[int] = None,
                   daily_minutes: Optional[int] = None, start_date: Optional[str] = None,
                   prefer: Optional[str] = None, use_ai: bool = True, variant: int = 0,
                   history: Optional[List[dict]] = None, memory: Optional[dict] = None) -> dict:
    ref = timeutil.today()
    courses = schedule.user_courses(db, user)
    course_names = list(dict.fromkeys(c.course_name for c in courses))
    parsed = parse_request(message, ref, course_names)
    parsed["raw"] = message
    _merge_memory(parsed, memory, ref)
    pref = prefs_service.effective(db, user)
    notices: List[str] = []

    # 快捷按钮显式传入的参数优先
    if start_date:
        parsed["start"] = timeutil.parse_date(start_date, parsed["start"])
    parsed["prefer"] = prefer or parsed["prefer"]
    total_days = int(days or parsed["days"] or (14 if parsed["exam"] else 7))
    if total_days > MAX_DAYS:
        notices.append(f"一次最多规划 {MAX_DAYS} 天，已截取前 {MAX_DAYS} 天")
    total_days = max(1, min(MAX_DAYS, total_days))
    if parsed.get("extended"):
        notices.append(f"本周只剩 {parsed['extended']} 天，已顺延到下周日")
    # 起始日早于今天：已经过去的日子无法再安排，只排今天及以后
    if parsed["start"] < ref:
        end = parsed["start"] + timedelta(days=total_days - 1)
        if end < ref:
            raise ApiError(422, f"{parsed['start'].strftime('%m/%d')}-{end.strftime('%m/%d')} 已经过去了，请换一个今天以后的日期")
        notices.append(f"{parsed['start'].strftime('%m/%d')} 到昨天已经过去，从今天开始安排")
        total_days = (end - ref).days + 1
        parsed["start"] = ref
    # 显式传入的每日时长视为最终值；文字里的时长按"轻松/冲刺"调整；都没有时用设置里的偏好或每日目标的 2 倍
    if daily_minutes:
        minutes = int(daily_minutes)
    else:
        base = parsed["daily_minutes"] or pref.get("daily_minutes") or max(60, int(user.daily_goal_minutes or 60) * 2)
        minutes = round(int(base) * parsed["intensity"])
    minutes = max(30, min(360, minutes))

    if not parsed["subjects"]:
        week_courses = schedule.courses_on_date(db, user, parsed["start"], courses)
        pool = [c.course_name for c in week_courses] or course_names
        parsed["subjects"] = list(dict.fromkeys(pool))[:3] or ["自主学习"]
        parsed["from_timetable"] = bool(pool)

    contexts = day_contexts(db, user, parsed["start"], total_days, parsed["prefer"], pref)
    course_count = sum(len(c["courses"]) for c in contexts)
    free_minutes = sum(s["minutes"] for c in contexts for s in c["free"])
    short_days = sum(1 for c in contexts if sum(s["minutes"] for s in c["free"]) < minutes)

    config = providers.resolve(db, user) if use_ai else None
    tasks, new_courses, advice, title = None, [], "", ""
    warnings: List[str] = []
    fallback_reason = None
    provider = "rule"
    if config is not None:
        try:
            result = llm.chat_json(config, _llm_messages(parsed, contexts, minutes, user, db, history or [], variant,
                                                          memory, pref))
            raw_tasks = result.get("tasks") or []
            tasks = _validate_ai_tasks(raw_tasks, contexts, minutes)
            new_courses, dropped_courses = _validate_ai_courses(result.get("courses") or [], user)
            dropped_tasks = len(raw_tasks) - len(tasks or []) if isinstance(raw_tasks, list) else 0
            if dropped_tasks > 0:
                warnings.append(f"模型给出的 {dropped_tasks} 个学习块不在空闲时段或超出每日时长，已剔除")
            if dropped_courses:
                warnings.append(f"{dropped_courses} 门课程信息不完整，已剔除")
            if tasks or new_courses:
                provider = "llm"
                advice = str(result.get("advice") or "").strip()[:3000]
                title = str(result.get("title") or "").strip()[:40]
                tasks = tasks or []
                # 模型常常只排前一两天：有空闲却被漏掉的日子用规则引擎补齐
                covered = {t["date"] for t in tasks}
                missing = [c for c in contexts if c["date"].isoformat() not in covered
                           and sum(s["minutes"] for s in c["free"]) >= 30]
                if tasks and missing:
                    filler = _rule_tasks(missing, parsed["subjects"], minutes, parsed["intensity"], parsed["exam"],
                                         variant, pref.get("block_minutes"), pref.get("rest_minutes", 10))
                    if filler:
                        tasks = sorted(tasks + filler, key=lambda t: (t["date"], t["start_time"]))
                        warnings.append(f"模型漏排了 {len(missing)} 天，已按你的空闲时段自动补齐")
            else:
                fallback_reason = "模型给出的安排都不在你的空闲时段内"
        except llm.LlmError as error:
            logger.warning("模型调用失败，回退规则引擎：%s", error.message)
            fallback_reason = error.message
    if provider == "rule":
        tasks = _rule_tasks(contexts, parsed["subjects"], minutes, parsed["intensity"], parsed["exam"], variant,
                            pref.get("block_minutes"), pref.get("rest_minutes", 10))
        new_courses, warnings = [], []
        advice, title = "", ""

    title = title or _title(parsed, total_days)
    advice = advice or _rule_advice(parsed, minutes, total_days, tasks, short_days)
    planned = sum(t["duration_minutes"] for t in tasks)
    end = parsed["start"] + timedelta(days=total_days - 1)
    hours, rest = divmod(planned, 60)
    reply = (
        f"为你生成了「{title}」：{parsed['start'].strftime('%m/%d')} 起共 {total_days} 天，"
        f"{len(tasks)} 个学习块，合计 {hours} 小时 {rest} 分钟"
        + (f"，另识别到 {len(new_courses)} 门新课程。" if new_courses else "。")
        + ("" if tasks or new_courses else "这段时间没有足够的空闲，可以换个日期或减少每天时长试试。")
    )
    insights = [
        f"已避开 {course_count} 节课程与已有安排，找到 {free_minutes // 60} 小时 {free_minutes % 60} 分钟空闲",
        f"每天上限 {minutes} 分钟，段间休息 {pref.get('rest_minutes', 10)} 分钟，{pref.get('latest') or '22:00'} 后不安排，午饭和晚饭时间保持空出",
        f"时段偏好（{prefs_service.describe(pref)}）",
    ]
    if parsed.get("from_memory"):
        insights.append("沿用上一轮的科目：" + "、".join(parsed["subjects"]))
    model_label = f"{config.name} · {config.model}" if provider == "llm" and config else "本地规则引擎"
    return {
        "title": title,
        "goal": message.strip()[:200],
        "advice": advice,
        "reply": reply,
        "summary": reply,
        "provider": provider,
        "model": model_label,
        "fallback_reason": fallback_reason,
        "warnings": notices + warnings,
        "memory": _memory_out(parsed, parsed["start"], total_days, minutes, memory),
        "start_date": parsed["start"].isoformat(),
        "end_date": end.isoformat(),
        "days": total_days,
        "daily_minutes": minutes,
        "subjects": parsed["subjects"],
        "exam": parsed["exam"],
        "prefer": parsed["prefer"],
        "tasks": tasks,
        "courses": new_courses,
        "stats": {"task_count": len(tasks), "total_minutes": planned, "course_count": course_count,
                  "free_minutes": free_minutes, "new_courses": len(new_courses)},
        "insights": insights,
    }


def commit_draft(db: Session, user: User, draft: dict) -> dict:
    """把草稿写入日程：任务进入新学习计划，课程进入课表（冲突的课程跳过并说明原因）。"""
    tasks = (draft.get("tasks") or []) if draft.get("import_tasks", True) else []
    courses = (draft.get("courses") or []) if draft.get("import_courses", True) else []
    if not tasks and not courses:
        raise ApiError(422, "计划里没有可导入的任务或课程")

    plan = None
    if tasks:
        plan = StudyPlan(
            user_id=user.id,
            title=str(draft.get("title") or "AI 学习计划")[:200],
            goal=draft.get("goal"),
            description=draft.get("advice") or draft.get("summary"),
            start_date=draft.get("start_date"),
            end_date=draft.get("end_date"),
            duration_days=int(draft.get("days") or 7),
            available_hours=round(sum(int(t["duration_minutes"]) for t in tasks) / 60),
            status="active",
            source="ai",
            content=json.dumps({"insights": draft.get("insights", []), "provider": draft.get("provider"),
                                "model": draft.get("model")}, ensure_ascii=False),
        )
        db.add(plan)
        db.flush()
        for item in tasks:
            task = StudyTask(
                user_id=user.id,
                plan_id=plan.id,
                title=item["title"],
                subject=item.get("subject") or None,
                note=item.get("note") or None,
                priority=int(item.get("priority") or 2),
                source="ai",
                status="todo",
            )
            apply_schedule(task, item["date"], item.get("start_time"), int(item["duration_minutes"]))
            db.add(task)
        db.flush()
        db.refresh(plan)

    saved, skipped = [], []
    for item in courses:
        try:
            course = schedule.save_course(db, user, dict(item))
            saved.append(schedule.course_to_dict(course, int(user.total_weeks or 20)))
        except ApiError as error:
            skipped.append({"course_name": item["course_name"], "reason": error.message})
    return {"plan": plan, "courses_saved": saved, "courses_skipped": skipped}
