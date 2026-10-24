# -*- coding: utf-8 -*-
"""
课表导入的公共环节：预览数据组装、单门课程校验、写库。

Excel / 教务网页 / AI 识别三种来源解析出的课程都走这里，保证预览格式与写库逻辑完全一致。
"""

import re
from typing import Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core import timeutil
from app.core.errors import ApiError
from app.models import ImportLog, Timetable, User
from app.services import gamification, schedule

MAX_WEEKS = 30
_SEMESTER_RE = re.compile(r"^\d{4}-\d{4}-[123]$")
WEEKDAY_MAP = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}


def parse_day(value) -> Optional[int]:
    """1-7、"3"、"周三"、"星期日"、"Wed" 都能识别；无法识别返回 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        day = int(value)
        return day if 1 <= day <= 7 else None
    text = str(value or "").strip()
    for char, number in WEEKDAY_MAP.items():
        if char in text:
            return number
    english = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    lowered = text.lower()
    for index, prefix in enumerate(english, start=1):
        if lowered.startswith(prefix):
            return index
    match = re.search(r"[1-7]", text)
    return int(match.group(0)) if match else None


def _to_int(value) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        match = re.search(r"\d+", str(value or ""))
        return int(match.group(0)) if match else None


def normalize_course(raw: dict, user: User, total_weeks: int) -> Tuple[Optional[dict], Optional[str]]:
    """
    把外部来源（模型输出 / 前端回传）的一门课校验为标准结构。
    返回 (course, None) 或 (None, 跳过原因)。周次超出 total_weeks 视为无效。
    """
    if not isinstance(raw, dict):
        return None, "数据格式不正确"
    name = str(raw.get("course_name") or raw.get("name") or "").strip()
    if not name:
        return None, "缺少课程名称"
    day = parse_day(raw.get("day_of_week"))
    if day is None:
        return None, "星期无法识别"
    p1, p2 = _to_int(raw.get("start_period")), _to_int(raw.get("end_period"))
    if p1 is None:
        return None, "缺少节次"
    p2 = p1 if p2 is None else p2
    limit = len(schedule.period_times(user))
    if p1 < 1 or p2 < p1 or p2 > limit:
        return None, f"节次 {p1}-{p2} 超出节次表（共 {limit} 节）"

    weeks_value = raw.get("weeks")
    if isinstance(weeks_value, (list, tuple)) and weeks_value:
        numbers = {_to_int(w) for w in weeks_value}
        if None in numbers:
            return None, "周次格式不正确"
        weeks = sorted(numbers)
    elif isinstance(weeks_value, str) and weeks_value.strip():
        weeks = schedule.parse_week_text(weeks_value, MAX_WEEKS)
    elif str(raw.get("week_text") or "").strip():
        weeks = schedule.parse_week_text(str(raw["week_text"]), MAX_WEEKS)
    else:
        weeks = list(range(1, total_weeks + 1))
    if not weeks:
        return None, f"周次无法识别：{raw.get('week_text') or weeks_value}"
    if weeks[0] < 1 or weeks[-1] > total_weeks:
        return None, f"周次需在 1-{total_weeks} 周之间"

    return {
        "course_name": name[:160],
        "teacher": str(raw.get("teacher") or "").strip()[:120],
        "classroom": str(raw.get("classroom") or "").strip()[:80],
        "day_of_week": day,
        "start_period": p1,
        "end_period": p2,
        "weeks": weeks,
        "week_text": schedule.format_weeks(weeks),
    }, None


def widen_total_weeks(courses: Iterable[dict], total: int) -> int:
    """课程里出现了超过当前学期周数的周次（如 1-18 周，而用户设置是 16 周），把总周数放宽到能容纳。"""
    highest = max((max(c["weeks"]) for c in courses if c.get("weeks")), default=0)
    return min(MAX_WEEKS, max(total, highest))


def with_times(user: User, courses: Iterable[dict]) -> List[dict]:
    """补上 start_time / end_time / color，得到预览用的课程列表。"""
    preview = []
    for item in courses:
        start, end = schedule.periods_to_times(user, item["start_period"], item["end_period"])
        preview.append({**item, "start_time": start, "end_time": end, "color": schedule.color_for(item["course_name"])})
    return preview


def build_preview(db: Session, user: User, *, file_name: Optional[str], fmt: str, courses: List[dict],
                  skipped: List[dict], semester: Optional[str], semester_start: Optional[str],
                  total_weeks: Optional[int], **extra) -> dict:
    preview = with_times(user, courses)
    return {
        "file_name": file_name,
        "format": fmt,
        "semester": semester or schedule.effective_semester(db, user),
        "semester_start": semester_start,
        "total_weeks": total_weeks or int(user.total_weeks or 20),
        "courses": preview,
        "skipped": skipped,
        "success_count": len(preview),
        "fail_count": len(skipped),
        **extra,
    }


def select_indexes(courses: List[dict], selected: Optional[str]) -> List[dict]:
    """selected 为逗号分隔的预览序号；None 表示全部。"""
    if selected is None:
        return courses
    indexes = {int(part) for part in selected.split(",") if part.strip().isdigit()}
    chosen = [item for index, item in enumerate(courses) if index in indexes]
    if not chosen:
        raise ApiError(422, "请至少勾选一门课程")
    return chosen


def commit_courses(db: Session, user: User, *, semester: str, courses: List[dict], replace: bool = True,
                   semester_start: Optional[str] = None, total_weeks: Optional[int] = None,
                   file_name: Optional[str] = None, fail_count: int = 0) -> dict:
    """
    写入课程（courses 需已包含 start_time / end_time / color，即 with_times 的结果），
    同步学期设置，记录导入日志并结算成就奖励。返回 reward。
    """
    if not courses:
        raise ApiError(422, "请至少勾选一门课程")
    if semester_start and timeutil.parse_date(semester_start) is None:
        raise ApiError(422, "开学日期格式不正确")
    tracker = gamification.RewardTracker(db, user)
    user.semester = semester
    if semester_start:
        user.semester_start = semester_start
    if total_weeks:
        user.total_weeks = total_weeks
    if replace:
        db.query(Timetable).filter(Timetable.user_id == user.id, Timetable.semester == semester).delete()
    for item in courses:
        db.add(
            Timetable(
                user_id=user.id, semester=semester, course_name=item["course_name"], teacher=item["teacher"],
                classroom=item["classroom"], day_of_week=item["day_of_week"], start_period=item["start_period"],
                end_period=item["end_period"], start_time=item["start_time"], end_time=item["end_time"],
                weeks=",".join(map(str, item["weeks"])), week_text=item["week_text"], color=item["color"],
            )
        )
    db.add(ImportLog(user_id=user.id, import_type="timetable", file_name=(file_name or "")[:200] or None,
                     success_count=len(courses), fail_count=fail_count))
    db.flush()
    reward = tracker.finish()
    db.commit()
    return reward


def valid_semester(value: Optional[str]) -> Optional[str]:
    return value if value and _SEMESTER_RE.match(value) else None
