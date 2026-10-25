# -*- coding: utf-8 -*-
"""课表接口：周视图、课程增删改（带冲突检测）、学期设置。"""

import json
import secrets
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core import timeutil
from app.core.errors import ApiError, ok
from app.models import ImportLog, Timetable, TimetableShare, User
from app.schemas import CourseIn, ShareImportIn, TimetableSettingsIn
from app.services import gamification, schedule

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


def _load_share(db, code: str) -> TimetableShare:
    share = db.query(TimetableShare).filter(TimetableShare.code == schedule.normalize_share_code(code)).first()
    if share is None:
        raise ApiError(404, "分享码不存在，请检查是否输入正确")
    if share.expires_at and share.expires_at < timeutil.now():
        raise ApiError(410, "分享码已过期，请让同学重新生成")
    return share


def _share_dict(db, share: TimetableShare, user: User) -> dict:
    payload = json.loads(share.payload)
    owner = db.get(User, share.user_id)
    return {
        "code": share.code,
        "semester": share.semester,
        "owner_name": (owner.full_name or owner.username) if owner else "已注销的同学",
        "owner_avatar": (owner.avatar if owner else None) or "🦉",
        "is_mine": share.user_id == user.id,
        "course_count": len(payload.get("courses") or []),
        "courses": payload.get("courses") or [],
        "period_times": payload.get("period_times") or [],
        "total_weeks": payload.get("total_weeks"),
        "semester_start": payload.get("semester_start"),
        "import_count": int(share.import_count or 0),
        "expires_at": share.expires_at.isoformat() if share.expires_at else None,
        "created_at": share.created_at.isoformat() if share.created_at else None,
    }


@router.post("/share", summary="生成课表分享码（当前学期课程 + 节次设置快照，7 天有效）")
def create_share(user: CurrentUser, db: DB):
    snapshot = schedule.share_snapshot(db, user)
    if not snapshot["courses"]:
        raise ApiError(422, "当前学期还没有课程，先添加或导入课表再分享")
    code = ""
    for _ in range(20):
        code = "".join(secrets.choice(schedule.SHARE_ALPHABET) for _ in range(8))
        if not db.query(TimetableShare.id).filter(TimetableShare.code == code).first():
            break
    share = TimetableShare(
        user_id=user.id, code=code, semester=snapshot["semester"],
        payload=json.dumps(snapshot, ensure_ascii=False),
        expires_at=timeutil.now() + timedelta(days=schedule.SHARE_DAYS),
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return ok(_share_dict(db, share, user), "分享码已生成，7 天内有效")


@router.get("/share/{code}", summary="预览分享的课表（课程列表、分享者昵称）")
def preview_share(code: str, user: CurrentUser, db: DB):
    return ok(_share_dict(db, _load_share(db, code), user))


@router.post("/share/{code}/import", summary="把分享的课表导入到自己的当前学期（冲突的课跳过并说明原因）")
def import_share(code: str, payload: ShareImportIn, user: CurrentUser, db: DB):
    share = _load_share(db, code)
    snapshot = json.loads(share.payload)
    tracker = gamification.RewardTracker(db, user)
    result = schedule.import_shared_courses(db, user, snapshot, payload.mode, payload.use_period_times)
    if result["added_count"]:
        share.import_count = int(share.import_count or 0) + 1
        db.add(ImportLog(user_id=user.id, import_type="share", file_name=f"分享码 {share.code}",
                         success_count=result["added_count"], fail_count=result["skipped_count"]))
    db.flush()
    result["reward"] = tracker.finish()
    db.commit()
    db.refresh(user)
    result["timetable"] = timetable_payload(db, user)
    if not result["added_count"]:
        message = "没有导入新课程" + (f"，{result['skipped_count']} 门已跳过" if result["skipped_count"] else "")
    elif result["skipped_count"]:
        message = f"已导入 {result['added_count']} 门课，{result['skipped_count']} 门因冲突跳过"
    else:
        message = f"已导入 {result['added_count']} 门课"
    return ok(result, message)


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
