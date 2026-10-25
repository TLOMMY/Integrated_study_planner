# -*- coding: utf-8 -*-
"""
任务接口。路径沿用小组"接口整合锁死版"：/task/list、/task/create、/task/update/{id}、
/task/complete/{id}、/task/delete/{id}，新增 /task/uncomplete/{id}。
"""

from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Query
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.api.deps import DB, CurrentUser
from app.core import timeutil
from app.core.errors import ApiError, ok
from app.models import FocusRecord, StudyTask
from app.schemas import TaskBatchIn, TaskChecklistIn, TaskIn, TaskListRenameIn, TaskUpdateIn
from app.services import tasks as task_service

router = APIRouter(prefix="/task", tags=["任务"])

View = Literal["today", "upcoming", "overdue", "completed", "range", "all"]


@router.get("/list", summary="任务列表（今日 / 即将 / 逾期 / 已完成 / 日期区间）")
def list_tasks(
    user: CurrentUser,
    db: DB,
    view: View = "today",
    date: Optional[str] = Query(default=None, description="参考日期，默认今天"),
    start: Optional[str] = None,
    end: Optional[str] = None,
    plan_id: Optional[int] = None,
    q: Optional[str] = Query(default=None, max_length=50, description="按标题 / 科目 / 备注 / 标签 / 清单搜索；配合 view=all 搜全部任务"),
    list_name: Optional[str] = Query(default=None, max_length=20, description="只看某个清单；传空串表示未归入清单的任务"),
    tag: Optional[str] = Query(default=None, max_length=12, description="只看带某个标签的任务"),
):
    ref = timeutil.parse_date(date, timeutil.today())
    key = ref.isoformat()
    query = task_service.visible_tasks(
        db.query(StudyTask).options(joinedload(StudyTask.plan)).filter(StudyTask.user_id == user.id)
    )
    if q and q.strip():
        like = f"%{q.strip().replace('%', '').replace('_', '')}%"
        query = query.filter(or_(StudyTask.title.ilike(like), StudyTask.subject.ilike(like), StudyTask.note.ilike(like),
                                 StudyTask.tags.ilike(like), StudyTask.list_name.ilike(like)))
    if plan_id is not None:
        query = query.filter(StudyTask.plan_id == plan_id)
    if list_name is not None:
        name = list_name.strip()
        query = query.filter(StudyTask.list_name == name if name else StudyTask.list_name.is_(None))
    tag = (tag or "").strip().lstrip("#")
    if tag:
        query = query.filter(StudyTask.tags.like(task_service.tag_like(tag), escape="\\"))

    if view == "today":
        query = query.filter(StudyTask.due_date == key)
    elif view == "overdue":
        query = query.filter(StudyTask.completed.is_(False), StudyTask.due_date < key)
    elif view == "upcoming":
        query = query.filter(StudyTask.completed.is_(False)).filter(
            (StudyTask.due_date > key) | (StudyTask.due_date.is_(None))
        )
    elif view == "completed":
        query = query.filter(StudyTask.completed.is_(True))
    elif view == "range":
        range_start = timeutil.parse_date(start, ref)
        range_end = timeutil.parse_date(end, range_start)
        if range_end < range_start:
            raise ApiError(422, "结束日期不能早于开始日期")
        query = query.filter(StudyTask.due_date >= range_start.isoformat(), StudyTask.due_date <= range_end.isoformat())

    items = query.all()
    if tag:
        items = [task for task in items if tag in task_service.task_tags(task)]
    if view == "all":
        items.sort(key=lambda t: (bool(t.completed), t.due_date or "9999-12-31", t.id))
        items = items[:50]
    elif view == "completed":
        items.sort(key=lambda t: t.completed_at or t.updated_at, reverse=True)
        items = items[:100]
    else:
        far = timeutil.combine(ref, "23:59")
        items.sort(key=lambda t: (bool(t.completed), t.due_date or "9999-12-31", t.start_time or far, -int(t.priority or 0), t.id))

    return ok(
        {
            "view": view,
            "date": key,
            "items": [task_service.task_to_dict(task, ref) for task in items],
            "total": len(items),
            "counts": task_service.task_counts(db, user, ref),
        }
    )


@router.get("/detail/{task_id}", summary="任务详情")
def task_detail(task_id: int, user: CurrentUser, db: DB):
    return ok(task_service.task_to_dict(task_service.get_owned_task(db, user, task_id)))


@router.post("/create", summary="创建任务")
def create_task(payload: TaskIn, user: CurrentUser, db: DB):
    if payload.plan_id is not None:
        task_service.get_owned_plan(db, user, payload.plan_id)
    due = payload.due_date or (timeutil.today().isoformat() if payload.start_time else None)
    task = StudyTask(
        user_id=user.id,
        plan_id=payload.plan_id,
        title=payload.title,
        subject=payload.subject or None,
        note=payload.note or None,
        priority=payload.priority,
        repeat_rule=payload.repeat_rule,
        source=payload.source,
        status="todo",
    )
    task_service.apply_schedule(task, due, payload.start_time, payload.duration_minutes)
    task_service.apply_extras(task, payload.model_dump(exclude_unset=True))
    db.add(task)
    db.commit()
    db.refresh(task)
    return ok(task_service.task_to_dict(task), "任务已创建")


@router.put("/update/{task_id}", summary="修改任务（只更新传入的字段）")
def update_task(task_id: int, payload: TaskUpdateIn, user: CurrentUser, db: DB):
    task = task_service.get_owned_task(db, user, task_id)
    changes = payload.model_dump(exclude_unset=True)
    if "plan_id" in changes and changes["plan_id"] is not None:
        task_service.get_owned_plan(db, user, changes["plan_id"])
    for field in ("title", "subject", "note", "priority", "repeat_rule", "plan_id"):
        if field in changes and (changes[field] is not None or field in ("plan_id", "subject", "note")):
            setattr(task, field, changes[field])
    if {"due_date", "start_time", "duration_minutes"} & changes.keys():
        due = changes["due_date"] if "due_date" in changes else task.due_date
        start = (
            changes["start_time"]
            if "start_time" in changes
            else (task.start_time.strftime("%H:%M") if task.start_time else None)
        )
        if start and not due:
            due = timeutil.today().isoformat()
        duration = changes.get("duration_minutes") or int(task.duration_minutes or 30)
        old_anchor = task_service.task_anchor(task)
        task_service.apply_schedule(task, due, start, duration)
        # 没有同时改提醒时，提醒跟着任务一起平移
        if "remind_at" not in changes:
            task_service.shift_reminder(task, old_anchor)
    task_service.apply_extras(task, changes)
    db.commit()
    db.refresh(task)
    return ok(task_service.task_to_dict(task), "任务已更新")


@router.put("/checklist/{task_id}", summary="整体保存子任务（勾选、增删、排序）")
def save_checklist(task_id: int, payload: TaskChecklistIn, user: CurrentUser, db: DB):
    task = task_service.get_owned_task(db, user, task_id)
    task_service.apply_extras(task, {"checklist": payload.checklist})
    db.commit()
    db.refresh(task)
    return ok(task_service.task_to_dict(task), "子任务已保存")


@router.get("/lists", summary="清单与标签（含任务数 / 未完成数）")
def list_groups(user: CurrentUser, db: DB):
    return ok(task_service.group_summary(db, user))


@router.put("/lists/rename", summary="重命名清单或标签（新名字已存在时合并）")
def rename_group(payload: TaskListRenameIn, user: CurrentUser, db: DB):
    if payload.old_name == payload.new_name:
        return ok({"count": 0}, "名称没有变化")
    count = task_service.rename_group(db, user, payload.kind, payload.old_name, payload.new_name)
    if not count:
        raise ApiError(404, "没有找到这个清单或标签")
    db.commit()
    label = "清单" if payload.kind == "list" else "标签"
    return ok({"count": count}, f"已把{label}「{payload.old_name}」改名为「{payload.new_name}」")


@router.delete("/lists/{name}", summary="删除清单或标签（只去掉名字，任务保留）")
def clear_group(name: str, user: CurrentUser, db: DB, kind: Literal["list", "tag"] = "list"):
    name = name.strip()
    if not name:
        raise ApiError(422, "请指定清单或标签名")
    count = task_service.clear_group(db, user, kind, name)
    db.commit()
    label = "清单" if kind == "list" else "标签"
    return ok({"count": count}, f"已删除{label}「{name}」，{count} 个任务保留")


@router.get("/reminders", summary="未来一段时间内需要提醒的未完成任务（网页提醒与手机本地通知共用）")
def upcoming_reminders(user: CurrentUser, db: DB, days: int = Query(default=7, ge=1, le=14)):
    now = timeutil.now()
    rows = (
        task_service.visible_tasks(
            db.query(StudyTask).filter(
                StudyTask.user_id == user.id,
                StudyTask.completed.is_(False),
                StudyTask.remind_at.isnot(None),
                StudyTask.remind_at >= now - timedelta(hours=1),
                StudyTask.remind_at <= now + timedelta(days=days),
            )
        )
        .order_by(StudyTask.remind_at)
        .limit(200)
        .all()
    )
    items = [
        {
            "id": task.id,
            "title": task.title,
            "remind_at": task.remind_at.strftime("%Y-%m-%dT%H:%M"),
            "due_date": task.due_date,
            "start_time": task.start_time.strftime("%H:%M") if task.start_time else None,
            "subject": task.subject or "",
        }
        for task in rows
    ]
    return ok({"items": items, "now": now.strftime("%Y-%m-%dT%H:%M:%S")})


@router.put("/complete/{task_id}", summary="完成任务，返回 XP / 成就回执")
def complete_task(task_id: int, user: CurrentUser, db: DB):
    task = task_service.get_owned_task(db, user, task_id)
    result = task_service.complete_task(db, user, task)
    db.commit()
    return ok(result, "任务已完成")


@router.put("/uncomplete/{task_id}", summary="撤销完成（同时收回该任务的 XP）")
def uncomplete_task(task_id: int, user: CurrentUser, db: DB):
    task = task_service.get_owned_task(db, user, task_id)
    result = task_service.uncomplete_task(db, user, task)
    db.commit()
    return ok(result, "已恢复为未完成")


@router.post("/batch", summary="批量删除 / 移动任务（移动时保留原来的时刻与时长）")
def batch_tasks(payload: TaskBatchIn, user: CurrentUser, db: DB):
    ids = list(dict.fromkeys(payload.ids))
    tasks = db.query(StudyTask).filter(StudyTask.user_id == user.id, StudyTask.id.in_(ids)).all()
    if len(tasks) != len(ids):
        raise ApiError(404, "部分任务不存在或已被删除，请刷新后重试")
    if payload.action == "delete":
        db.query(FocusRecord).filter(FocusRecord.task_id.in_(ids)).update({"task_id": None}, synchronize_session=False)
        db.query(StudyTask).filter(StudyTask.repeat_parent_id.in_(ids)).update({"repeat_parent_id": None}, synchronize_session=False)
        for task in tasks:
            db.delete(task)
        db.commit()
        return ok({"ids": ids, "count": len(ids)}, f"已删除 {len(ids)} 个任务")
    target = timeutil.parse_date(payload.due_date, None) if payload.due_date else None
    for task in tasks:
        if target:
            day = target
        else:
            base = timeutil.parse_date(task.due_date, None) or timeutil.today()
            day = base + timedelta(days=payload.shift_days)
        start_hm = task.start_time.strftime("%H:%M") if task.start_time else None
        old_anchor = task_service.task_anchor(task)
        task_service.apply_schedule(task, day.isoformat(), start_hm, int(task.duration_minutes or 25))
        task_service.shift_reminder(task, old_anchor)
    db.commit()
    label = target.strftime("%m/%d") if target else f"{'后' if payload.shift_days > 0 else '前'} {abs(payload.shift_days)} 天"
    return ok({"ids": ids, "count": len(ids)}, f"已把 {len(ids)} 个任务移到{label}")


@router.delete("/delete/{task_id}", summary="删除任务")
def delete_task(task_id: int, user: CurrentUser, db: DB):
    task = task_service.get_owned_task(db, user, task_id)
    db.query(FocusRecord).filter(FocusRecord.task_id == task.id).update({"task_id": None})
    db.delete(task)
    db.commit()
    return ok({"id": task_id}, "任务已删除")
