# -*- coding: utf-8 -*-
"""考试倒计时。"""

from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core.errors import ok
from app.models import Exam
from app.schemas import ExamIn, ExamUpdateIn
from app.services.exams import exam_to_dict, get_owned_exam, list_exams

# 不设 prefix：本模块内的路径写完整（如 /exams），由 main.py 统一注册
router = APIRouter(tags=["考试"])


@router.get("/exams", summary="考试列表：upcoming 按日期升序（含今天），past 为已结束的（最近的在前）")
def get_exams(user: CurrentUser, db: DB):
    return ok(list_exams(db, user))


@router.post("/exams", summary="添加考试")
def create_exam(payload: ExamIn, user: CurrentUser, db: DB):
    exam = Exam(user_id=user.id, **payload.model_dump())
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return ok(exam_to_dict(exam), "考试已添加")


@router.put("/exams/{exam_id}", summary="修改考试")
def update_exam(exam_id: int, payload: ExamUpdateIn, user: CurrentUser, db: DB):
    exam = get_owned_exam(db, user, exam_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in ("title", "exam_date") and not value:
            continue
        setattr(exam, key, value)
    db.commit()
    db.refresh(exam)
    return ok(exam_to_dict(exam), "考试已更新")


@router.delete("/exams/{exam_id}", summary="删除考试")
def delete_exam(exam_id: int, user: CurrentUser, db: DB):
    exam = get_owned_exam(db, user, exam_id)
    db.delete(exam)
    db.commit()
    return ok({"id": exam_id}, "考试已删除")
