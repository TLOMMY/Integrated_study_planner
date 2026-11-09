# -*- coding: utf-8 -*-
"""
一键排今天：在本地按规则把待办填进今天剩下的空闲段，不调用大模型、不消耗 AI 额度。

排的顺序（越靠前越先占位置）：
1. 真实待办：逾期的 → 今天没定时间的 → 收集箱里高 / 中优先级的（按优先级、时长）；
2. 考前复习：14 天内有考试、且今天还没有该科目任务的，每科一段，越临近越长；
3. 课后回顾（可选，默认不勾选）：今天已经上完的课，每门 15 分钟。

空闲段与日程页一致（planner.free_slots：避开课程前后 10 分钟、饭点、现在以前、偏好之外的时段），
每段之间留出休息时间，合计不超过每日上限（设置里的每日时长，没设时 3 小时），不把空闲全部塞满。
预览只计算不写库；确认后由 commit() 逐条写入，每条单独校验并返回失败原因。
"""

from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.ai.planner import free_slots
from app.core import timeutil
from app.core.errors import ApiError
from app.models import Exam, StudyTask, User
from app.services import prefs as prefs_service
from app.services import schedule
from app.services.tasks import apply_schedule, get_owned_task, task_to_dict, visible_tasks

EXAM_DAYS = 14
DEFAULT_DAILY_CAP = 180
REVIEW_MINUTES = 15
MIN_BLOCK = 15
MAX_BLOCK = 120
INBOX_LIMIT = 3


def _hm(minutes: int) -> str:
    return timeutil.minutes_to_hm(minutes)


def _exam_minutes(days_left: int) -> int:
    """离考试越近，复习越长：3 天内 60 分钟，7 天内 45 分钟，其余 30 分钟。"""
    return 60 if days_left <= 3 else 45 if days_left <= 7 else 30


def _candidates(db: Session, user: User, day: date) -> List[dict]:
    today = day.isoformat()
    open_tasks = visible_tasks(db.query(StudyTask).filter(StudyTask.user_id == user.id, StudyTask.completed.is_(False))).all()

    def task_item(task: StudyTask, reason: str, kind: str) -> dict:
        return {"kind": "task", "group": kind, "task_id": task.id, "title": task.title, "subject": task.subject or "",
                "minutes": max(MIN_BLOCK, min(MAX_BLOCK, int(task.duration_minutes or 30))),
                "priority": int(task.priority or 0), "reason": reason, "optional": False}

    overdue = sorted((t for t in open_tasks if t.due_date and t.due_date < today and not t.repeat_parent_id),
                     key=lambda t: (-int(t.priority or 0), t.due_date, t.id))
    untimed = sorted((t for t in open_tasks if t.due_date == today and not t.start_time),
                     key=lambda t: (-int(t.priority or 0), t.id))
    inbox = sorted((t for t in open_tasks if not t.due_date and int(t.priority or 0) >= 2),
                   key=lambda t: (-int(t.priority or 0), int(t.duration_minutes or 30), t.id))[:INBOX_LIMIT]
    items = [task_item(t, "已逾期", "overdue") for t in overdue]
    items += [task_item(t, "今天要做", "today") for t in untimed]
    items += [task_item(t, "收集箱", "inbox") for t in inbox]

    # 今天已经排了这个科目的任务时，不再加考前复习
    subjects_today = {(t.subject or "").strip() for t in open_tasks if t.due_date == today and t.subject}
    exams = (db.query(Exam).filter(Exam.user_id == user.id, Exam.exam_date > today,
                                   Exam.exam_date <= (day + timedelta(days=EXAM_DAYS)).isoformat())
             .order_by(Exam.exam_date).all())
    seen = set()
    for exam in exams:
        subject = (exam.subject or exam.title).strip()
        if not subject or subject in seen or subject in subjects_today:
            continue
        seen.add(subject)
        days_left = (timeutil.parse_date(exam.exam_date) - day).days
        items.append({"kind": "exam", "group": "exam", "exam_id": exam.id, "title": f"{subject}：考前复习",
                      "subject": subject, "minutes": _exam_minutes(days_left), "priority": 3 if days_left <= 3 else 2,
                      "reason": f"离考试 {days_left} 天", "optional": False})

    # 课后回顾：只针对今天已经上完的课，同名课一天只回顾一次
    now_hm = timeutil.now().strftime("%H:%M") if day == timeutil.today() else "23:59"
    reviewed = set()
    for course in schedule.courses_on_date(db, user, day):
        name = course.course_name
        if course.end_time > now_hm or name in reviewed or name in subjects_today:
            continue
        reviewed.add(name)
        items.append({"kind": "review", "group": "review", "title": f"回顾今天的{name}笔记", "subject": name,
                      "minutes": REVIEW_MINUTES, "priority": 1, "reason": "课后回顾", "optional": True,
                      "after": timeutil.hm_to_minutes(course.end_time)})
    return items


def _busy(db: Session, user: User, day: date) -> List[tuple]:
    busy = [(c.start_time, c.end_time) for c in schedule.courses_on_date(db, user, day)]
    timed = visible_tasks(db.query(StudyTask).filter(
        StudyTask.user_id == user.id, StudyTask.due_date == day.isoformat(),
        StudyTask.start_time.isnot(None), StudyTask.completed.is_(False))).all()
    busy += [(t.start_time.strftime("%H:%M"), t.end_time.strftime("%H:%M")) for t in timed if t.end_time]
    return busy


def preview(db: Session, user: User, day: Optional[date] = None) -> dict:
    """计算今天的排法（不写库）。"""
    day = day or timeutil.today()
    if day < timeutil.today():
        raise ApiError(422, "不能给已经过去的日期排程")
    pref = prefs_service.effective(db, user)
    rest = int(pref.get("rest_minutes") or 10)
    cap = int(pref.get("daily_minutes") or DEFAULT_DAILY_CAP)
    slots = [{"start": timeutil.hm_to_minutes(s["start"]), "end": timeutil.hm_to_minutes(s["end"])}
             for s in free_slots(_busy(db, user, day), day, pref=pref)]
    free_total = sum(s["end"] - s["start"] for s in slots)

    placed, skipped, used = [], [], 0
    for item in _candidates(db, user, day):
        if used + item["minutes"] > cap and not item["optional"]:
            skipped.append({**item, "why": "超过今天的学习上限"})
            continue
        # 课后回顾只能排在那节课下课以后
        after = item.pop("after", 0)
        slot = next((s for s in slots if max(s["start"], after) + item["minutes"] <= s["end"]), None)
        if slot is None:
            skipped.append({**item, "why": "没有足够长的空闲段"})
            continue
        start = max(slot["start"], after)
        placed.append({**item, "date": day.isoformat(), "start_time": _hm(start), "end_time": _hm(start + item["minutes"])})
        if start - slot["start"] >= MIN_BLOCK:
            # 前面空出来的一截保留下来，给后面的条目用
            slots.insert(slots.index(slot), {"start": slot["start"], "end": start - rest})
        slot["start"] = start + item["minutes"] + rest
        if not item["optional"]:
            used += item["minutes"]
    placed.sort(key=lambda p: p["start_time"])
    for index, item in enumerate(placed):
        item["key"] = f"a{index}"
    return {
        "date": day.isoformat(),
        "items": placed,
        "skipped": [{"title": s["title"], "reason": s["why"]} for s in skipped],
        "free_minutes": free_total,
        "planned_minutes": sum(p["minutes"] for p in placed if not p["optional"]),
        "cap_minutes": cap,
    }


def commit(db: Session, user: User, items: List[dict]) -> dict:
    """写入勾选的条目：已有任务改到这个时段，考前复习 / 课后回顾新建任务。逐条校验，返回每条结果。"""
    from app.ai.agent import Checker  # 与 AI 提案共用同一套时间校验

    checker = Checker(db, user)
    results = []
    for raw in items:
        key, title = raw.get("key"), str(raw.get("title") or "").strip()[:200]
        day, start = str(raw.get("date") or ""), str(raw.get("start_time") or "")
        minutes = int(raw.get("minutes") or 0)
        if not timeutil.parse_date(day) or not title or not MIN_BLOCK <= minutes <= MAX_BLOCK:
            results.append({"key": key, "ok": False, "title": title or "未命名", "reason": "条目不完整"})
            continue
        task = None
        if raw.get("kind") == "task":
            try:
                task = get_owned_task(db, user, int(raw.get("task_id") or 0))
            except ApiError:
                results.append({"key": key, "ok": False, "title": title, "reason": "任务不存在或已删除"})
                continue
            if task.completed:
                results.append({"key": key, "ok": False, "title": title, "reason": "任务已经完成了"})
                continue
            checker.exclude.add(task.id)
        errors, _ = checker.task_issues(day, start, minutes)
        if errors:
            results.append({"key": key, "ok": False, "title": title, "reason": "；".join(errors)})
            continue
        before = None
        if task is None:
            task = StudyTask(user_id=user.id, title=title, subject=(raw.get("subject") or "")[:80] or None,
                             priority=max(0, min(3, int(raw.get("priority") or 0))), source="auto", status="todo")
            db.add(task)
        else:
            before = {"due_date": task.due_date, "start_time": task.start_time.strftime("%H:%M") if task.start_time else None,
                      "duration_minutes": int(task.duration_minutes or 30)}
        apply_schedule(task, day, start, minutes)
        db.flush()
        checker.include(task, created=before is None)
        results.append({"key": key, "ok": True, "title": task.title, "id": task.id, "created": before is None,
                        "before": before, "task": task_to_dict(task)})
    db.commit()
    ok_count = sum(1 for r in results if r["ok"])
    return {"results": results, "ok_count": ok_count, "fail_count": len(results) - ok_count}
