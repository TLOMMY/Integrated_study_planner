"""旧库升级：模拟阶段一/二留下的表结构，确认迁移后外键正确、旧数据可用。"""

import sqlite3
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import Session

from app.core.migrate import repair_data, sync_schema
from app.models import StudyTask, Timetable, User

LEGACY_SQL = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50), email VARCHAR(100), hashed_password VARCHAR(200),
                    full_name VARCHAR(100), is_active BOOLEAN, created_at DATETIME, updated_at DATETIME);
CREATE TABLE study_plans (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), title VARCHAR(200),
                          duration_days INTEGER, status VARCHAR(20), created_at DATETIME);
CREATE TABLE study_tasks (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                          plan_id INTEGER REFERENCES study_plans(id), title VARCHAR(200), subject VARCHAR(80),
                          start_time DATETIME, end_time DATETIME, duration_minutes INTEGER, completed BOOLEAN,
                          status VARCHAR(20), note TEXT, created_at DATETIME, updated_at DATETIME);
CREATE INDEX ix_study_tasks_id ON study_tasks (id);
CREATE TABLE timetables (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), course_name VARCHAR(160),
                         teacher VARCHAR(80), classroom VARCHAR(80), day_of_week INTEGER, start_time VARCHAR(10),
                         end_time VARCHAR(10), semester VARCHAR(40), color VARCHAR(20), created_at DATETIME);
ALTER TABLE users RENAME TO users_legacy_stage2;
CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50) UNIQUE, email VARCHAR(100) UNIQUE,
                    hashed_password VARCHAR(200), full_name VARCHAR(100), is_active BOOLEAN,
                    created_at DATETIME, updated_at DATETIME);
INSERT INTO users VALUES (7, 'old', 'old@example.com', 'x', '老用户', 1, NULL, NULL);
INSERT INTO study_plans VALUES (3, 7, '旧计划', 7, 'active', '2026-05-01 10:00:00');
INSERT INTO study_tasks VALUES (11, 7, 99, '孤儿任务', NULL, '2026-06-11 19:00:00', '2026-06-11 20:00:00', 60, 0,
                                'todo', NULL, NULL, NULL);
INSERT INTO timetables VALUES (5, 7, '旧课程', NULL, 'A101', 2, '10:00', '11:40', '2025-2026-1', '#2563eb', NULL);
"""


def test_legacy_database_is_upgraded():
    path = Path(tempfile.mkdtemp()) / "legacy.db"
    raw = sqlite3.connect(path)
    raw.executescript(LEGACY_SQL)
    raw.close()

    engine = create_engine(f"sqlite:///{path.as_posix()}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    sync_schema(engine)

    inspector = inspect(engine)
    for table in ("study_plans", "study_tasks", "timetables"):
        targets = {fk["referred_table"] for fk in inspector.get_foreign_keys(table)}
        assert "users_legacy_stage2" not in targets, table
    assert "due_date" in {c["name"] for c in inspector.get_columns("study_tasks")}

    with Session(engine) as db:
        repair_data(db)
        task = db.get(StudyTask, 11)
        assert task.plan_id is None and task.due_date == "2026-06-11"
        course = db.get(Timetable, 5)
        assert (course.start_period, course.end_period) == (3, 4)
        assert db.get(User, 7).semester == "2025-2026-1"
        # 外键开启后仍可正常写入
        db.add(StudyTask(user_id=7, title="新任务", plan_id=3))
        db.commit()
    engine.dispose()
