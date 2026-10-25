# -*- coding: utf-8 -*-
"""学习计划、任务、课程表、专注记录与导入日志。"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.timeutil import now


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    goal = Column(Text, nullable=True)
    available_hours = Column(Integer, default=0)
    duration_days = Column(Integer, default=7)
    difficulty = Column(String(20), default="medium")
    content = Column(Text, nullable=True)
    # active / completed / archived
    status = Column(String(20), default="active")
    # manual / ai
    source = Column(String(20), default="manual")
    start_date = Column(String(10), nullable=True)
    end_date = Column(String(10), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    # 回收站：删除时只记录时间，30 天后自动彻底删除
    deleted_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    tasks = relationship("StudyTask", back_populates="plan", cascade="all, delete-orphan")


class StudyTask(Base):
    __tablename__ = "study_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("study_plans.id"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    subject = Column(String(80), nullable=True)
    note = Column(Text, nullable=True)

    # 日期是任务归属的主键；start_time 只在"定了具体时刻"时才有值
    due_date = Column(String(10), nullable=True, index=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, default=60)

    # 0 无 / 1 低 / 2 中 / 3 高，对应滴答清单的四级优先级
    priority = Column(Integer, default=0)
    # none / daily / weekdays / weekly
    repeat_rule = Column(String(20), default="none")
    repeat_parent_id = Column(Integer, nullable=True, index=True)

    completed = Column(Boolean, default=False)
    status = Column(String(20), default="todo")
    completed_at = Column(DateTime, nullable=True)

    # 番茄钟联动：累计专注分钟与完整番茄数
    focus_minutes = Column(Integer, default=0)
    pomodoros = Column(Integer, default=0)

    # manual / ai / repeat / quick
    source = Column(String(20), default="manual")

    # v4：标签（JSON 字符串数组）、清单分组名、子任务（JSON：[{id,title,done}]）、
    #     学习资源链接（JSON：[{title,url,source}]，如 AI 推荐的 B 站课程）、提醒时间
    tags = Column(Text, nullable=True)
    list_name = Column(String(40), nullable=True, index=True)
    checklist = Column(Text, nullable=True)
    links = Column(Text, nullable=True)
    remind_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)

    plan = relationship("StudyPlan", back_populates="tasks")


class Timetable(Base):
    __tablename__ = "timetables"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_name = Column(String(160), nullable=False)
    teacher = Column(String(120), nullable=True)
    classroom = Column(String(80), nullable=True)
    day_of_week = Column(Integer, nullable=False)

    # 节次是课表网格的真实坐标；start_time/end_time 由节次时间表推导，便于时间轴使用
    start_period = Column(Integer, nullable=True)
    end_period = Column(Integer, nullable=True)
    start_time = Column(String(10), nullable=False)
    end_time = Column(String(10), nullable=False)

    # 上课周次，逗号分隔的完整列表，如 "2,4,6,8"；week_text 是给人看的 "2-8周(双)"
    weeks = Column(Text, nullable=True)
    week_text = Column(String(80), nullable=True)

    semester = Column(String(40), default="2025-2026-1")
    color = Column(String(20), default="#4F6EF7")
    note = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=now)


class FocusRecord(Base):
    __tablename__ = "focus_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("study_tasks.id"), nullable=True)
    record_date = Column(String(20), nullable=False, index=True)
    duration_minutes = Column(Integer, default=0)
    planned_minutes = Column(Integer, nullable=True)
    # True 表示按计划完整跑完一个番茄；提前结束只按实际分钟计
    completed = Column(Boolean, default=True)
    subject = Column(String(80), nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    source = Column(String(40), default="timer")
    created_at = Column(DateTime, default=now)


class ImportLog(Base):
    __tablename__ = "import_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    import_type = Column(String(40), default="timetable")
    file_name = Column(String(200), nullable=True)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    imported_at = Column(DateTime, default=now)
