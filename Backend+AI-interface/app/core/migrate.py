# -*- coding: utf-8 -*-
"""
启动时的轻量迁移：建缺失的表、补缺失的列、修复旧数据。

项目早期没有用 Alembic，本地库里存在多个阶段留下的表结构。这里按模型元数据
逐表对比并 ALTER TABLE ADD COLUMN，保证旧库无需手动处理即可升级。
"""

import logging

from sqlalchemy import Boolean, Integer, inspect, text
from sqlalchemy.orm import Session

from app.core.database import Base, engine

logger = logging.getLogger("study_planner.migrate")

# 早期版本留下、现已无模型对应的表
LEGACY_TABLES = {"users_legacy_stage2", "badges", "plans", "tasks", "study_records"}


def _default_sql(column) -> str:
    default = column.default
    if default is None or not getattr(default, "is_scalar", False):
        return ""
    value = default.arg
    if isinstance(column.type, Boolean):
        return f" DEFAULT {1 if value else 0}"
    if isinstance(column.type, Integer):
        return f" DEFAULT {int(value)}"
    escaped = str(value).replace("'", "''")
    return f" DEFAULT '{escaped}'"


def _rebuild_broken_foreign_keys(bind) -> None:
    """
    早期版本执行过 ALTER TABLE users RENAME TO users_legacy_stage2，SQLite 会把所有
    外键自动改指向旧表。这里按模型重建这些表（保留数据），让外键重新指向 users。
    """
    inspector = inspect(bind)
    existing = set(inspector.get_table_names())
    model_tables = {table.name for table in Base.metadata.sorted_tables}
    broken = [
        table
        for table in Base.metadata.sorted_tables
        if table.name in existing
        and any(fk["referred_table"] not in model_tables for fk in inspector.get_foreign_keys(table.name))
    ]
    if not broken:
        return
    with bind.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        # 重命名时不改写其他表对它的引用，新表建好后引用自然指向新表
        conn.exec_driver_sql("PRAGMA legacy_alter_table=ON")
        conn.commit()
        try:
            for table in broken:
                old = f"_old_{table.name}"
                for row in conn.exec_driver_sql(f'PRAGMA index_list("{table.name}")').fetchall():
                    if row[3] == "c":
                        conn.exec_driver_sql(f'DROP INDEX "{row[1]}"')
                conn.exec_driver_sql(f'ALTER TABLE "{table.name}" RENAME TO "{old}"')
                table.create(bind=conn)
                old_columns = {row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info("{old}")')}
                columns = ", ".join(f'"{c.name}"' for c in table.columns if c.name in old_columns)
                conn.exec_driver_sql(f'INSERT INTO "{table.name}" ({columns}) SELECT {columns} FROM "{old}"')
                conn.exec_driver_sql(f'DROP TABLE "{old}"')
                logger.info("migrate: rebuilt %s to fix foreign keys", table.name)
            conn.commit()
        finally:
            conn.exec_driver_sql("PRAGMA legacy_alter_table=OFF")
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            conn.commit()


def sync_schema(bind=None) -> None:
    import app.models  # noqa: F401 - 注册全部模型到 Base.metadata

    bind = bind or engine
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "sqlite":
        _rebuild_broken_foreign_keys(bind)
    inspector = inspect(bind)
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                col_type = column.type.compile(dialect=bind.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}{_default_sql(column)}'))
                logger.info("migrate: added %s.%s", table.name, column.name)
        for table in Base.metadata.sorted_tables:
            for index in table.indexes:
                index.create(bind=conn, checkfirst=True)


def repair_data(db: Session) -> None:
    from app.models import StudyPlan, StudyTask, Timetable, User
    from app.services import schedule

    # 外键开启前留下的孤儿引用
    db.execute(text("UPDATE study_tasks SET plan_id = NULL WHERE plan_id IS NOT NULL AND plan_id NOT IN (SELECT id FROM study_plans)"))
    db.execute(text("UPDATE focus_records SET task_id = NULL WHERE task_id IS NOT NULL AND task_id NOT IN (SELECT id FROM study_tasks)"))

    # 旧任务只有 start_time，没有归属日期
    for task in db.query(StudyTask).filter(StudyTask.due_date.is_(None), StudyTask.start_time.isnot(None)):
        task.due_date = task.start_time.date().isoformat()
    for task in db.query(StudyTask).filter(StudyTask.completed.is_(True), StudyTask.completed_at.is_(None)):
        task.completed_at = task.updated_at or task.start_time or task.created_at

    # 旧计划没有起止日期
    for plan in db.query(StudyPlan).filter(StudyPlan.start_date.is_(None)):
        if plan.created_at:
            plan.start_date = plan.created_at.date().isoformat()

    users = {user.id: user for user in db.query(User).all()}
    # 旧课程只有时间，没有节次
    for course in db.query(Timetable).filter(Timetable.start_period.is_(None)):
        owner = users.get(course.user_id)
        if owner is None:
            continue
        course.start_period = schedule.time_to_period(owner, course.start_time)
        course.end_period = max(course.start_period, schedule.time_to_period(owner, course.end_time, use_end=True))

    for user in users.values():
        if not user.semester:
            user.semester = schedule.effective_semester(db, user)
    db.commit()


def drop_legacy_tables(bind=None) -> list:
    """删除早期版本遗留、已无任何模型使用的空表（有数据的一律保留，不做破坏性操作）。"""
    bind = bind or engine
    dropped = []
    existing = set(inspect(bind).get_table_names())
    with bind.begin() as conn:
        for name in LEGACY_TABLES & existing:
            if conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar() == 0:
                conn.execute(text(f'DROP TABLE "{name}"'))
                dropped.append(name)
    return sorted(dropped)


def init_database() -> None:
    sync_schema()
    drop_legacy_tables()
    from app.core.database import SessionLocal
    from app.core.config import settings

    db = SessionLocal()
    try:
        repair_data(db)
        if settings.SEED_DEMO:
            from app.services.seed import ensure_demo

            ensure_demo(db)
    finally:
        db.close()
