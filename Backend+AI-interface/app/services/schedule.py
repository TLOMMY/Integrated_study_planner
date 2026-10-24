# -*- coding: utf-8 -*-
"""
课程表领域逻辑（对标 WakeUp 课程表）：节次时间、周次解析、教学周计算、冲突检测。
"""

import json
import re
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import timeutil
from app.core.errors import ApiError
from app.models import Timetable, User

DEFAULT_PERIOD_TIMES: List[Dict[str, str]] = [
    {"start": "08:00", "end": "08:45"},
    {"start": "08:50", "end": "09:35"},
    {"start": "09:55", "end": "10:40"},
    {"start": "10:45", "end": "11:30"},
    {"start": "14:00", "end": "14:45"},
    {"start": "14:50", "end": "15:35"},
    {"start": "15:55", "end": "16:40"},
    {"start": "16:45", "end": "17:30"},
    {"start": "19:00", "end": "19:45"},
    {"start": "19:50", "end": "20:35"},
    {"start": "20:40", "end": "21:25"},
    {"start": "21:30", "end": "22:15"},
]

PALETTE = ["#4F6EF7", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4", "#EC4899", "#84CC16", "#F97316", "#14B8A6"]

_SEGMENT = re.compile(r"(\d+)\s*(?:-\s*(\d+))?\s*周?\s*(?:\(\s*([单双])\s*\)|（\s*([单双])\s*）)?")


# ---------------------------------------------------------------- 节次
def period_times(user: User) -> List[Dict[str, str]]:
    if user.period_times:
        try:
            parsed = json.loads(user.period_times)
            if isinstance(parsed, list) and parsed and all("start" in p and "end" in p for p in parsed):
                return parsed
        except (TypeError, ValueError):
            pass
    return DEFAULT_PERIOD_TIMES


def periods_to_times(user: User, start_period: int, end_period: int) -> tuple:
    table = period_times(user)
    start_period = max(1, min(start_period, len(table)))
    end_period = max(start_period, min(end_period, len(table)))
    return table[start_period - 1]["start"], table[end_period - 1]["end"]


def time_to_period(user: User, hm: str, use_end: bool = False) -> int:
    """把旧数据里的 "08:00" 映射到最接近的节次。"""
    table = period_times(user)
    target = timeutil.hm_to_minutes(hm)
    key = "end" if use_end else "start"
    return 1 + min(range(len(table)), key=lambda i: abs(timeutil.hm_to_minutes(table[i][key]) - target))


# ---------------------------------------------------------------- 周次
def parse_week_text(text: str, total_weeks: int = 30) -> List[int]:
    """
    解析正方教务风格的周次："2-16周(双)"、"1-3周,18周"、"9-17周(单)"、"14周"。
    """
    weeks = set()
    for chunk in re.split(r"[,，、]", str(text or "")):
        match = _SEGMENT.search(chunk)
        if not match:
            continue
        start = int(match.group(1))
        end = int(match.group(2) or start)
        parity = match.group(3) or match.group(4)
        for week in range(min(start, end), max(start, end) + 1):
            if parity == "单" and week % 2 == 0:
                continue
            if parity == "双" and week % 2 == 1:
                continue
            if 1 <= week <= total_weeks:
                weeks.add(week)
    return sorted(weeks)


def format_weeks(weeks: Iterable[int]) -> str:
    """把周次列表还原成紧凑可读文本，如 [2,4,6,8] -> "2-8周(双)"。"""
    items = sorted(set(int(w) for w in weeks))
    if not items:
        return ""
    if len(items) >= 3:
        step_two = all(b - a == 2 for a, b in zip(items, items[1:]))
        if step_two:
            parity = "单" if items[0] % 2 else "双"
            return f"{items[0]}-{items[-1]}周({parity})"
    parts, run_start, previous = [], items[0], items[0]
    for week in items[1:] + [None]:
        if week is not None and week == previous + 1:
            previous = week
            continue
        parts.append(f"{run_start}-{previous}" if previous != run_start else f"{run_start}")
        if week is not None:
            run_start = previous = week
    return ",".join(parts) + "周"


def course_weeks(course: Timetable, total_weeks: int) -> List[int]:
    if course.weeks:
        return [int(w) for w in str(course.weeks).split(",") if w.strip().isdigit()]
    return list(range(1, total_weeks + 1))


def teaching_week(user: User, day: Optional[date] = None) -> Optional[int]:
    """返回 day 所在的教学周；未设置开学日期返回 None，学期外返回 0。"""
    start = timeutil.parse_date(user.semester_start)
    if start is None:
        return None
    day = day or timeutil.today()
    delta = (timeutil.monday_of(day) - timeutil.monday_of(start)).days // 7 + 1
    total = int(user.total_weeks or 20)
    return delta if 1 <= delta <= total else 0


def week_dates(user: User, week: int, fallback: Optional[date] = None) -> List[date]:
    start = timeutil.parse_date(user.semester_start)
    monday = (
        timeutil.monday_of(start) + timedelta(weeks=week - 1)
        if start
        else timeutil.monday_of(fallback or timeutil.today())
    )
    return [monday + timedelta(days=i) for i in range(7)]


# ---------------------------------------------------------------- 学期与查询
def guess_semester(day: Optional[date] = None) -> str:
    day = day or timeutil.today()
    if day.month >= 8:
        return f"{day.year}-{day.year + 1}-1"
    if day.month == 1:
        return f"{day.year - 1}-{day.year}-1"
    return f"{day.year - 1}-{day.year}-2"


def effective_semester(db: Session, user: User) -> str:
    if user.semester:
        return user.semester
    row = (
        db.query(Timetable.semester, func.count(Timetable.id))
        .filter(Timetable.user_id == user.id)
        .group_by(Timetable.semester)
        .order_by(func.count(Timetable.id).desc())
        .first()
    )
    return row[0] if row and row[0] else guess_semester()


def user_courses(db: Session, user: User) -> List[Timetable]:
    return (
        db.query(Timetable)
        .filter(Timetable.user_id == user.id, Timetable.semester == effective_semester(db, user))
        .order_by(Timetable.day_of_week, Timetable.start_time)
        .all()
    )


def courses_on_date(db: Session, user: User, day: date, courses: Optional[List[Timetable]] = None) -> List[Timetable]:
    """某一天真正要上的课：星期匹配，且当天所在教学周在课程周次内。"""
    courses = courses if courses is not None else user_courses(db, user)
    week = teaching_week(user, day)
    if week == 0:
        return []
    total = int(user.total_weeks or 20)
    return sorted(
        (
            c
            for c in courses
            if c.day_of_week == day.isoweekday() and (week is None or week in course_weeks(c, total))
        ),
        key=lambda c: c.start_time,
    )


def find_conflicts(
    courses: Iterable[Timetable],
    day_of_week: int,
    start_period: int,
    end_period: int,
    weeks: List[int],
    total_weeks: int,
    exclude_id: Optional[int] = None,
) -> List[dict]:
    conflicts = []
    wanted = set(weeks)
    for course in courses:
        if course.id == exclude_id or course.day_of_week != day_of_week:
            continue
        if (course.start_period or 0) > end_period or (course.end_period or 0) < start_period:
            continue
        overlap = wanted & set(course_weeks(course, total_weeks))
        if overlap:
            conflicts.append(
                {
                    "id": course.id,
                    "course_name": course.course_name,
                    "periods": f"{course.start_period}-{course.end_period}节",
                    "overlap_weeks": format_weeks(overlap),
                }
            )
    return conflicts


def save_course(db: Session, user: User, data: dict, course: Optional[Timetable] = None) -> Timetable:
    """
    新增或修改课程。data 字段同 CourseIn：course_name / day_of_week / start_period / end_period /
    weeks 或 week_text / teacher / classroom / color / note / force。时间冲突抛 409。
    """
    table = period_times(user)
    if int(data["end_period"]) > len(table):
        raise ApiError(422, f"当前节次表只有 {len(table)} 节")
    total = int(user.total_weeks or 20)
    if data.get("weeks"):
        weeks = sorted({int(w) for w in data["weeks"]})
    elif data.get("week_text"):
        weeks = parse_week_text(data["week_text"], total)
    else:
        weeks = list(range(1, total + 1))
    if not weeks or weeks[0] < 1 or weeks[-1] > total:
        raise ApiError(422, f"上课周次需在 1-{total} 周之间")

    day, p1, p2 = int(data["day_of_week"]), int(data["start_period"]), int(data["end_period"])
    if not data.get("force"):
        conflicts = find_conflicts(user_courses(db, user), day, p1, p2, weeks, total,
                                   exclude_id=course.id if course else None)
        if conflicts:
            first = conflicts[0]
            raise ApiError(409, f"与「{first['course_name']}」在{first['overlap_weeks']}时间冲突", {"conflicts": conflicts})

    course = course or Timetable(user_id=user.id, semester=effective_semester(db, user))
    course.course_name = data["course_name"]
    course.teacher = data.get("teacher") or ""
    course.classroom = data.get("classroom") or ""
    course.day_of_week = day
    course.start_period, course.end_period = p1, p2
    course.start_time, course.end_time = periods_to_times(user, p1, p2)
    course.weeks = ",".join(map(str, weeks))
    course.week_text = format_weeks(weeks)
    course.color = data.get("color") or course.color or color_for(data["course_name"])
    course.note = data.get("note") or ""
    db.add(course)
    db.flush()
    return course


def color_for(name: str) -> str:
    return PALETTE[sum(ord(ch) for ch in name or "") % len(PALETTE)]


def course_to_dict(course: Timetable, total_weeks: int, week: Optional[int] = None) -> dict:
    weeks = course_weeks(course, total_weeks)
    return {
        "id": course.id,
        "course_name": course.course_name,
        "teacher": course.teacher or "",
        "classroom": course.classroom or "",
        "day_of_week": course.day_of_week,
        "start_period": course.start_period,
        "end_period": course.end_period,
        "start_time": course.start_time,
        "end_time": course.end_time,
        "weeks": weeks,
        "week_text": course.week_text or format_weeks(weeks),
        "semester": course.semester,
        "color": course.color or color_for(course.course_name),
        "note": course.note or "",
        "in_week": True if week is None or week == 0 else week in weeks,
    }
