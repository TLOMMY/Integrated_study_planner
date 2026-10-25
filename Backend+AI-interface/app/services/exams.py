# -*- coding: utf-8 -*-
"""考试倒计时：按日期排序，区分即将到来与已结束。"""

from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core import timeutil
from app.core.errors import ApiError
from app.models import Exam, User

URGENT_DAYS = 3


def exam_to_dict(exam: Exam, today: Optional[date] = None) -> dict:
    today = today or timeutil.today()
    day = timeutil.parse_date(exam.exam_date)
    days_left = (day - today).days if day else None
    return {
        "id": exam.id,
        "title": exam.title,
        "subject": exam.subject or "",
        "exam_date": exam.exam_date,
        "start_time": exam.start_time or "",
        "location": exam.location or "",
        "note": exam.note or "",
        "weekday": timeutil.weekday_label(day) if day else "",
        "days_left": days_left,
        "urgent": days_left is not None and 0 <= days_left <= URGENT_DAYS,
        "is_past": days_left is not None and days_left < 0,
    }


def get_owned_exam(db: Session, user: User, exam_id: int) -> Exam:
    exam = db.query(Exam).filter(Exam.id == exam_id, Exam.user_id == user.id).first()
    if exam is None:
        raise ApiError(404, "考试不存在或已被删除")
    return exam


def list_exams(db: Session, user: User) -> dict:
    today = timeutil.today()
    rows = db.query(Exam).filter(Exam.user_id == user.id).order_by(Exam.exam_date, Exam.start_time, Exam.id).all()
    items = [exam_to_dict(e, today) for e in rows]
    upcoming = [e for e in items if not e["is_past"]]
    # 已结束的按时间倒序，最近考完的在前
    past = sorted((e for e in items if e["is_past"]), key=lambda e: (e["exam_date"], e["start_time"]), reverse=True)
    return {"upcoming": upcoming, "past": past, "today": today.isoformat()}


def upcoming_exams(db: Session, user: User, limit: int = 3) -> List[dict]:
    return list_exams(db, user)["upcoming"][:limit]
