# -*- coding: utf-8 -*-
"""课表接口：周视图、课程增删改（带冲突检测）、学期设置。"""

import json
from typing import Optional

from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core import timeutil
from app.core.errors import ApiError, ok
from app.models import Timetable, User
from app.schemas import CourseIn, TimetableSettingsIn
from app.services import schedule

router = APIRouter(prefix="/timetable", tags=["课表"])


def timetable_payload(db, user: User, week: Optional[int] = None) -> dict:
    total = int(user.total_weeks or 20)
    current = schedule.teaching_week(user)
    selected = week or (current if current else 1)
    selected = max(1, min(total, selected))
    dates = schedule.week_dates(user, selected)
    today = timeutil.today()
    courses = schedule.user_courses(db, user)
    return {
        "semester": schedule.effective_semester(db, user),
        "semester_start": user.semester_start,
        "settings_ready": bool(user.semester_start),
        "total_weeks": total,
        "current_week": current,
        "week": selected,
        "period_times": schedule.period_times(user),
        "days": [
            {"day_of_week": i + 1, "label": f"周{timeutil.WEEKDAY_CN[i]}", "date": d.isoformat(),
             "short": d.strftime("%m/%d"), "is_today": d == today}
            for i, d in enumerate(dates)
        ],
        "courses": [schedule.course_to_dict(c, total, selected if user.semester_start else None) for c in courses],
    }


def _save_course(db, user: User, payload: CourseIn, course: Optional[Timetable] = None) -> Timetable:
    return schedule.save_course(db, user, payload.model_dump(), course)


@router.get("", summary="课表（含教学周、节次时间、每门课是否在所选周）")
def get_timetable(user: CurrentUser, db: DB, week: Optional[int] = None):
    return ok(timetable_payload(db, user, week))


@router.put("/settings", summary="学期设置：学期名 / 开学日期 / 总周数 / 节次时间")
def update_settings(payload: TimetableSettingsIn, user: CurrentUser, db: DB):
    changes = payload.model_dump(exclude_unset=True)
    if "semester" in changes and changes["semester"]:
        old = schedule.effective_semester(db, user)
        if old != changes["semester"]:
            # 改学期名时把当前学期的课一并迁过去，避免课表"消失"
            db.query(Timetable).filter(Timetable.user_id == user.id, Timetable.semester == old).update(
                {"semester": changes["semester"]}
            )
        user.semester = changes["semester"]
    if "semester_start" in changes:
        user.semester_start = changes["semester_start"]
    if "total_weeks" in changes and changes["total_weeks"]:
        user.total_weeks = changes["total_weeks"]
    if changes.get("period_times"):
        user.period_times = json.dumps(changes["period_times"], ensure_ascii=False)
        for course in schedule.user_courses(db, user):
            course.start_time, course.end_time = schedule.periods_to_times(user, course.start_period or 1, course.end_period or 1)
    db.commit()
    db.refresh(user)
    return ok(timetable_payload(db, user), "学期设置已保存")


@router.post("", summary="添加课程（时间冲突返回 409，force=true 可强制保存）")
def create_course(payload: CourseIn, user: CurrentUser, db: DB):
    course = _save_course(db, user, payload)
    db.commit()
    return ok(schedule.course_to_dict(course, int(user.total_weeks or 20)), "课程已添加")


@router.put("/{course_id}", summary="修改课程")
def update_course(course_id: int, payload: CourseIn, user: CurrentUser, db: DB):
    course = db.query(Timetable).filter(Timetable.id == course_id, Timetable.user_id == user.id).first()
    if course is None:
        raise ApiError(404, "课程不存在或已被删除")
    course = _save_course(db, user, payload, course)
    db.commit()
    return ok(schedule.course_to_dict(course, int(user.total_weeks or 20)), "课程已更新")


@router.delete("/{course_id}", summary="删除课程")
def delete_course(course_id: int, user: CurrentUser, db: DB):
    deleted = db.query(Timetable).filter(Timetable.id == course_id, Timetable.user_id == user.id).delete()
    if not deleted:
        raise ApiError(404, "课程不存在或已被删除")
    db.commit()
    return ok({"id": course_id}, "课程已删除")
