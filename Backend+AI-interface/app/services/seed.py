# -*- coding: utf-8 -*-
"""
演示数据。

评审打开系统时需要一个"有生活气息"的账号：课表、计划、今日任务、连续打卡、
热力图、成就、排行榜都要有内容。演示账号 is_demo=True，排行榜里的同学也带
"演示"标记，不会和真实用户混淆。

命令行重置：python -m app.services.seed --reset
"""

import random
import secrets
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core import timeutil
from app.core.security import hash_password, verify_password
from app.models import FocusRecord, ImportLog, StudyPlan, StudyTask, Timetable, User, UserAchievement, XpEvent
from app.services import gamification, schedule
from app.services.tasks import apply_schedule, spawn_next

DEMO_USERNAME = "demo_user"
DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo123456"
SEED_MARKER = "v3"

PEERS = [
    ("peer_lin", "学霸小林", "🐼", 1.55),
    ("peer_zhe", "早起的阿哲", "🦊", 1.15),
    ("peer_qing", "图书馆常驻", "🐱", 0.85),
    ("peer_yu", "夜猫子小鱼", "🐟", 0.6),
    ("peer_ming", "慢慢来的明", "🐢", 0.35),
]

COURSES = [
    # 课程, 星期, 起节, 止节, 周次, 教室, 教师
    ("高等数学", 1, 1, 2, "1-16", "A1408", "王老师"),
    ("高等数学", 3, 3, 4, "1-16", "A1408", "王老师"),
    ("大学英语", 2, 1, 2, "1-16", "B2203", "李老师"),
    ("线性代数", 2, 5, 6, "1-12", "A1309", "陈老师"),
    ("大学物理", 4, 1, 2, "1-16", "A1308", "黄老师"),
    ("大学物理实验", 4, 5, 7, "2-16(双)", "实验楼 305", "黄老师"),
    ("C++ 程序设计", 1, 7, 8, "1-16", "机房 B203", "郭老师"),
    ("C++ 程序设计", 5, 3, 4, "1-16", "机房 B203", "郭老师"),
    ("中国近现代史纲要", 3, 5, 6, "1-18", "A2409", "崔老师"),
    ("体育", 5, 7, 8, "1-16", "东区体育馆", "张老师"),
    ("工程制图", 3, 7, 8, "1-9(单)", "A3405", "熊老师"),
]


def _weeks(text: str, total: int):
    return schedule.parse_week_text(text + "周" if "周" not in text else text, total)


def reset_demo(db: Session, user: User) -> None:
    uid = user.id
    for model in (FocusRecord, XpEvent, UserAchievement, ImportLog, StudyTask):
        db.query(model).filter(model.user_id == uid).delete(synchronize_session=False)
    db.query(StudyPlan).filter(StudyPlan.user_id == uid).delete(synchronize_session=False)
    db.query(Timetable).filter(Timetable.user_id == uid).delete(synchronize_session=False)
    db.flush()


def _seed_courses(db: Session, user: User) -> None:
    total = int(user.total_weeks)
    for name, day, p1, p2, weeks_text, room, teacher in COURSES:
        weeks = _weeks(weeks_text, total)
        start, end = schedule.periods_to_times(user, p1, p2)
        db.add(
            Timetable(
                user_id=user.id, course_name=name, teacher=teacher, classroom=room, day_of_week=day,
                start_period=p1, end_period=p2, start_time=start, end_time=end,
                weeks=",".join(map(str, weeks)), week_text=schedule.format_weeks(weeks),
                semester=user.semester, color=schedule.color_for(name),
            )
        )


def _task(db: Session, user: User, title: str, due: date = None, start: str = None, minutes: int = 45,
          subject: str = None, priority: int = 0, plan: StudyPlan = None, repeat: str = "none",
          done_at=None, note: str = None, source: str = "manual") -> StudyTask:
    task = StudyTask(user_id=user.id, title=title, subject=subject, priority=priority, repeat_rule=repeat,
                     plan_id=plan.id if plan else None, note=note, source=source, status="todo")
    apply_schedule(task, due.isoformat() if due else None, start, minutes)
    if done_at is not None:
        task.completed, task.status, task.completed_at = True, "completed", done_at
    db.add(task)
    db.flush()
    return task


def _seed_plans_and_tasks(db: Session, user: User, today: date) -> None:
    exam = StudyPlan(user_id=user.id, title="高数期中冲刺", goal="两周内吃透极限、导数与积分应用",
                     description="AI 根据课表空闲时段生成，每天约 90 分钟", source="ai", status="active",
                     start_date=(today - timedelta(days=4)).isoformat(), end_date=(today + timedelta(days=9)).isoformat(),
                     duration_days=14)
    project = StudyPlan(user_id=user.id, title="C++ 实训项目", goal="完成学习规划系统前后端联调与答辩材料",
                        source="manual", status="active", start_date=(today - timedelta(days=10)).isoformat(),
                        end_date=(today + timedelta(days=18)).isoformat(), duration_days=29)
    cet = StudyPlan(user_id=user.id, title="英语四级词汇", goal="背完核心词汇 2000 个", source="manual",
                    status="completed", start_date=(today - timedelta(days=40)).isoformat(),
                    end_date=(today - timedelta(days=12)).isoformat(), duration_days=29,
                    completed_at=timeutil.combine(today - timedelta(days=12), "21:30"))
    db.add_all([exam, project, cet])
    db.flush()

    at = lambda d, hm: timeutil.combine(today + timedelta(days=d), hm)  # noqa: E731
    for i, title in enumerate(["极限与连续：梳理知识框架", "导数：专项练习", "错题复盘：第一章"]):
        _task(db, user, title, today - timedelta(days=3 - i), "19:30", 45, "高等数学", 2, exam,
              done_at=at(i - 3, "20:20"), source="ai")
    _task(db, user, "积分应用：真题训练", today, "19:00", 50, "高等数学", 3, exam, source="ai",
          note="建议 2 个番茄，结束后休息 10 分钟")
    _task(db, user, "微分方程：梳理考点", today + timedelta(days=1), "20:00", 45, "高等数学", 2, exam, source="ai")
    _task(db, user, "限时模拟：期中样卷", today + timedelta(days=3), "14:00", 90, "高等数学", 3, exam, source="ai")

    _task(db, user, "后端接口联调", today - timedelta(days=2), "21:00", 60, "C++ 程序设计", 2, project,
          done_at=at(-2, "22:00"))
    _task(db, user, "前端课表页面重构", today, "20:10", 60, "C++ 程序设计", 2, project)
    _task(db, user, "准备答辩 PPT", today + timedelta(days=5), None, 90, "C++ 程序设计", 1, project)
    for i in range(6):
        _task(db, user, f"Unit {i + 1} 核心词汇", today - timedelta(days=40 - i * 5), None, 30, "大学英语", 1, cet,
              done_at=at(-40 + i * 5, "22:00"))

    words = _task(db, user, "背 30 个单词", today, "07:30", 20, "大学英语", 1, repeat="daily",
                  done_at=at(0, "07:52"))
    spawn_next(db, words)
    _task(db, user, "概率论作业 2.3", today - timedelta(days=1), None, 40, "概率论", 3)
    _task(db, user, "预习线性代数第三章", today + timedelta(days=1), None, 40, "线性代数", 1)
    _task(db, user, "大学物理期中复习", today + timedelta(days=5), None, 60, "大学物理", 2)
    _task(db, user, "读完《原则》第二部分", None, None, 30, None, 0)


def _focus_day(db: Session, user: User, day: date, minutes: int, rng: random.Random, early: bool = False) -> None:
    subjects = ["高等数学", "大学英语", "C++ 程序设计", "大学物理", "线性代数"]
    slots = ["07:20"] if early else []
    slots += ["14:10", "16:00", "19:30", "20:40", "21:20"]
    left, index = minutes, 0
    while left > 0 and index < len(slots):
        length = min(left, rng.choice([25, 25, 45, 50]))
        started = timeutil.combine(day, slots[index])
        db.add(FocusRecord(user_id=user.id, record_date=day.isoformat(), duration_minutes=length,
                           planned_minutes=length if length in (25, 45, 50) else 25, completed=True,
                           subject=rng.choice(subjects), started_at=started,
                           ended_at=started + timedelta(minutes=length), source="seed"))
        gamification.award(db, user.id, length, "focus", f"seed-{day}-{index}", on=day)
        gamification.award(db, user.id, gamification.XP_POMODORO_BONUS, "pomodoro", f"seed-{day}-{index}", on=day)
        left -= length
        index += 1
    db.flush()
    if minutes >= int(user.daily_goal_minutes or 60):
        gamification.award(db, user.id, gamification.XP_DAILY_GOAL, "daily_goal", day.isoformat(), on=day)


def _seed_history(db: Session, user: User, today: date) -> None:
    rng = random.Random(20260301)
    skip = {12, 27}
    for offset in range(45, 0, -1):
        if offset in skip or (offset > 27 and rng.random() < 0.25):
            continue
        day = today - timedelta(days=offset)
        _focus_day(db, user, day, rng.choice([35, 50, 60, 75, 90, 120, 150]), rng, early=offset == 9)
    # 今天先学了一点，留出"达成每日目标"的空间给评审现场体验
    _focus_day(db, user, today, 25, rng)
    for task in db.query(StudyTask).filter(StudyTask.user_id == user.id, StudyTask.completed.is_(True)):
        gamification.award(db, user.id, gamification.XP_TASK, "task", str(task.id), on=task.completed_at.date())


def _keep_streak_alive(db: Session, user: User, today: date) -> None:
    """演示账号几天后再打开，补上中间的空档，保证连续打卡仍在。"""
    latest = (
        db.query(FocusRecord.record_date)
        .filter(FocusRecord.user_id == user.id)
        .order_by(FocusRecord.record_date.desc())
        .first()
    )
    if latest is None:
        return
    cursor = date.fromisoformat(latest[0]) + timedelta(days=1)
    rng = random.Random(cursor.toordinal())
    while cursor < today:
        _focus_day(db, user, cursor, rng.choice([45, 60, 75, 90]), rng)
        cursor += timedelta(days=1)
    if cursor == today and latest[0] != today.isoformat():
        _focus_day(db, user, today, 25, rng)


def _ensure_peers(db: Session, demo: User, today: date) -> None:
    week_start = timeutil.monday_of(today)
    demo_week = sum(
        amount for (amount,) in db.query(XpEvent.amount).filter(XpEvent.user_id == demo.id, XpEvent.event_date >= week_start)
    )
    base = max(demo_week, 120)
    for username, name, avatar, ratio in PEERS:
        peer = db.query(User).filter(User.username == username).first()
        if peer is None:
            peer = User(username=username, email=f"{username}@demo.local", full_name=name, avatar=avatar,
                        hashed_password=hash_password(secrets.token_urlsafe(24)), is_demo=True, is_active=True)
            db.add(peer)
            db.flush()
        target = int(base * ratio)
        have = sum(
            amount for (amount,) in db.query(XpEvent.amount).filter(XpEvent.user_id == peer.id, XpEvent.event_date >= week_start)
        )
        if target > have:
            gamification.award(db, peer.id, target - have, "seed", f"{week_start}-{target}", on=today)


def seed_demo(db: Session, user: User) -> None:
    today = timeutil.today()
    user.full_name, user.avatar, user.is_demo = "演示同学", "🦉", True
    user.daily_goal_minutes = 60
    user.total_weeks = 20
    user.semester = schedule.guess_semester(today)
    user.semester_start = (timeutil.monday_of(today) - timedelta(weeks=7)).isoformat()
    user.period_times = None
    _seed_courses(db, user)
    _seed_plans_and_tasks(db, user, today)
    db.add(ImportLog(user_id=user.id, import_type="timetable", file_name="演示课表.xlsx", success_count=len(COURSES)))
    db.flush()
    _seed_history(db, user, today)
    gamification.evaluate_achievements(db, user.id)
    db.add(XpEvent(user_id=user.id, amount=0, reason="seed", ref=SEED_MARKER, event_date=today))
    db.flush()


def ensure_demo(db: Session) -> User:
    user = db.query(User).filter((User.username == DEMO_USERNAME) | (User.email == DEMO_EMAIL)).first()
    if user is None:
        user = User(username=DEMO_USERNAME, email=DEMO_EMAIL, hashed_password=hash_password(DEMO_PASSWORD),
                    is_demo=True, is_active=True)
        db.add(user)
        db.flush()
    if not verify_password(DEMO_PASSWORD, user.hashed_password):
        user.hashed_password = hash_password(DEMO_PASSWORD)
    seeded = db.query(XpEvent.id).filter_by(user_id=user.id, reason="seed", ref=SEED_MARKER).first()
    if not seeded:
        reset_demo(db, user)
        seed_demo(db, user)
    else:
        _keep_streak_alive(db, user, timeutil.today())
    _ensure_peers(db, user, timeutil.today())
    db.commit()
    return user


if __name__ == "__main__":
    import argparse

    from app.core.database import SessionLocal
    from app.core.migrate import sync_schema

    parser = argparse.ArgumentParser(description="演示数据工具")
    parser.add_argument("--reset", action="store_true", help="清空并重建演示账号数据")
    args = parser.parse_args()
    sync_schema()
    session = SessionLocal()
    try:
        demo = ensure_demo(session)
        if args.reset:
            reset_demo(session, demo)
            seed_demo(session, demo)
            _ensure_peers(session, demo, timeutil.today())
            session.commit()
        print(f"演示账号：{DEMO_EMAIL} / {DEMO_PASSWORD}")
    finally:
        session.close()
