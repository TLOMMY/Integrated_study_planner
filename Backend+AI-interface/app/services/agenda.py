# -*- coding: utf-8 -*-
"""
日程聚合：把"当天的课 + 定时任务 + 空闲时段"合成一条时间轴，首页与日视图共用。
"""

from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.ai.planner import free_slots
from app.core import timeutil
from app.models import StudyTask, User
from app.services import gamification, schedule
from app.services.accounts import user_to_dict
from app.services.tasks import task_counts, task_to_dict, visible_tasks


def _status(day: date, start: str, end: str) -> str:
    today = timeutil.today()
    if day < today:
        return "done"
    if day > today:
        return "upcoming"
    current = timeutil.now().strftime("%H:%M")
    if current >= end:
        return "done"
    return "ongoing" if current >= start else "upcoming"


def build_day(db: Session, user: User, day: date) -> dict:
    courses = schedule.courses_on_date(db, user, day)
    tasks = visible_tasks(
        db.query(StudyTask)
        .options(joinedload(StudyTask.plan))
        .filter(StudyTask.user_id == user.id, StudyTask.due_date == day.isoformat())
    ).all()
    timed = [t for t in tasks if t.start_time]
    untimed = sorted((t for t in tasks if not t.start_time), key=lambda t: (t.completed, -int(t.priority or 0), t.id))

    items = []
    for course in courses:
        items.append(
            {
                "type": "course",
                "id": f"course-{course.id}",
                "ref_id": course.id,
                "title": course.course_name,
                "start_time": course.start_time,
                "end_time": course.end_time,
                "location": course.classroom or "",
                "teacher": course.teacher or "",
                "periods": f"第 {course.start_period}-{course.end_period} 节",
                "color": course.color or schedule.color_for(course.course_name),
                "status": _status(day, course.start_time, course.end_time),
            }
        )
    for task in timed:
        data = task_to_dict(task)
        items.append(
            {
                "type": "task",
                "id": f"task-{task.id}",
                "ref_id": task.id,
                "title": task.title,
                "start_time": data["start_time"],
                "end_time": data["end_time"],
                "completed": data["completed"],
                "priority": data["priority"],
                "status": "done" if task.completed else _status(day, data["start_time"], data["end_time"]),
                "task": data,
            }
        )

    busy = [(item["start_time"], item["end_time"]) for item in items]
    free = [slot for slot in free_slots(busy, day) if slot["minutes"] >= 45]
    for slot in free:
        items.append(
            {
                "type": "free",
                "id": f"free-{slot['start']}",
                "title": "空闲时段",
                "start_time": slot["start"],
                "end_time": slot["end"],
                "minutes": slot["minutes"],
                "segment": slot["segment"],
            }
        )
    items.sort(key=lambda item: (item["start_time"], item["type"] == "free"))

    # 没有日期的待办只挂在"今天"，避免在日程里完全找不到
    undated = []
    if day == timeutil.today():
        undated = visible_tasks(
            db.query(StudyTask).options(joinedload(StudyTask.plan))
            .filter(StudyTask.user_id == user.id, StudyTask.due_date.is_(None), StudyTask.completed.is_(False))
        ).order_by(StudyTask.priority.desc(), StudyTask.id.desc()).limit(20).all()

    return {
        "date": day.isoformat(),
        "weekday": timeutil.weekday_label(day),
        "teaching_week": schedule.teaching_week(user, day),
        "items": items,
        "unscheduled": [task_to_dict(task) for task in untimed],
        "undated": [task_to_dict(task) for task in undated],
        "summary": {
            "courses": len(courses),
            "tasks": len(tasks),
            "tasks_done": sum(1 for task in tasks if task.completed),
            "free_minutes": sum(slot["minutes"] for slot in free),
        },
    }


def _greeting(hour: int) -> str:
    if hour < 5:
        return "夜深了"
    if hour < 11:
        return "早上好"
    if hour < 13:
        return "中午好"
    if hour < 18:
        return "下午好"
    return "晚上好"


def home_summary(db: Session, user: User, day: date) -> dict:
    agenda = build_day(db, user, day)
    current = timeutil.now()
    courses = [item for item in agenda["items"] if item["type"] == "course"]
    next_course = next((c for c in courses if c["status"] in ("ongoing", "upcoming")), None)
    minutes_until = None
    if next_course and next_course["status"] == "upcoming" and day == current.date():
        minutes_until = timeutil.hm_to_minutes(next_course["start_time"]) - (current.hour * 60 + current.minute)
    return {
        "date": agenda["date"],
        "weekday": agenda["weekday"],
        "greeting": _greeting(current.hour),
        "user": user_to_dict(user),
        "semester": schedule.effective_semester(db, user),
        "teaching_week": agenda["teaching_week"],
        "total_weeks": int(user.total_weeks or 20),
        "courses": courses,
        "next_course": next_course,
        "minutes_until_next": minutes_until,
        "free_minutes": agenda["summary"]["free_minutes"],
        "task_counts": task_counts(db, user, day),
        "daily_goal": gamification.daily_goal_info(db, user, day),
        "streak": gamification.streak_info(db, user.id),
        "level": gamification.level_info(gamification.total_xp(db, user.id)),
    }
