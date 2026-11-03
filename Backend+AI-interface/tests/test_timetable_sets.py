"""多套课表——新建、重命名、切换、整套删除、导入到新课表、旧数据迁移回填、读课程只看生效那套。"""

import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path

from conftest import body
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core import timeutil
from app.core.migrate import repair_data, sync_schema
from app.models import Timetable, TimetableSet


def _course(client, headers, **fields):
    payload = {"course_name": "高等数学", "day_of_week": 1, "start_period": 1, "end_period": 2, **fields}
    return body(client.post("/timetable", headers=headers, json=payload))


def _names(client, headers):
    return sorted(c["course_name"] for c in body(client.get("/timetable", headers=headers))["courses"])


def test_new_user_has_virtual_default_set(client, auth):
    data = body(client.get("/timetable", headers=auth))
    assert data["sets"]["active_id"] is None and data["sets"]["active_name"] == "我的课表"
    assert [s["name"] for s in data["sets"]["items"]] == ["我的课表"]
    # 第一次加课时才真正建出"我的课表"
    _course(client, auth)
    sets = body(client.get("/timetable/sets", headers=auth))
    assert sets["active_id"] and sets["items"][0]["course_count"] == 1 and sets["items"][0]["is_active"]


def test_create_switch_isolated_and_settings_follow(client, auth):
    start = timeutil.monday_of(timeutil.today()) - timedelta(weeks=2)
    body(client.put("/timetable/settings", headers=auth, json={"semester_start": start.isoformat(), "total_weeks": 18}))
    weekday = timeutil.today().isoweekday()
    _course(client, auth, day_of_week=weekday)
    first = body(client.get("/timetable/sets", headers=auth))["active_id"]

    # 新建（沿用设置）并切换：空课表，学期设置相同
    data = body(client.post("/timetable/sets", headers=auth, json={"name": "辅修"}))
    assert data["courses"] == [] and data["sets"]["active_name"] == "辅修"
    assert data["total_weeks"] == 18 and data["current_week"] == 3
    second = data["sets"]["active_id"]
    _course(client, auth, course_name="法学导论", day_of_week=weekday)
    # 在辅修里改学期设置，不影响"我的课表"
    body(client.put("/timetable/settings", headers=auth, json={"total_weeks": 12}))

    # 同名不能重复
    body(client.post("/timetable/sets", headers=auth, json={"name": "辅修"}), 409)

    data = body(client.post(f"/timetable/sets/{first}/activate", headers=auth))
    assert [c["course_name"] for c in data["courses"]] == ["高等数学"]
    assert data["total_weeks"] == 18 and data["sets"]["active_id"] == first
    items = {s["name"]: s for s in data["sets"]["items"]}
    assert items["辅修"]["total_weeks"] == 12 and items["辅修"]["course_count"] == 1

    # 日程、智能体工具、分享快照都只看生效那套
    day = body(client.get("/day/timeline", headers=auth, params={"date": timeutil.today().isoformat()}))
    titles = {i["title"] for i in day["items"] if i["type"] == "course"}
    assert titles == {"高等数学"}
    from app.ai import agent
    from app.core.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        uid = db.query(TimetableSet.user_id).filter(TimetableSet.id == first).scalar()
        listed = agent.tool_list_courses(db, db.get(User, uid), {})
        assert [c["name"] for c in listed["courses"]] == ["高等数学"]
        other = db.query(Timetable).filter(Timetable.set_id == second).first()
    finally:
        db.close()
    share = body(client.post("/timetable/share", headers=auth))
    assert [c["course_name"] for c in share["courses"]] == ["高等数学"]

    # 非生效课表里的课不能直接改 / 删
    body(client.put(f"/timetable/{other.id}", headers=auth,
                    json={"course_name": "x", "day_of_week": 1, "start_period": 1, "end_period": 2}), 404)
    body(client.delete(f"/timetable/{other.id}", headers=auth), 404)

    # 重命名
    data = body(client.put(f"/timetable/sets/{second}", headers=auth, json={"name": "法学辅修"}))
    assert {s["name"] for s in data["sets"]["items"]} == {"我的课表", "法学辅修"}


def test_sets_are_per_user(client, register):
    alice, _ = register()
    bob, _ = register()
    _course(client, alice)
    alice_set = body(client.get("/timetable/sets", headers=alice))["active_id"]
    body(client.post(f"/timetable/sets/{alice_set}/activate", headers=bob), 404)
    body(client.put(f"/timetable/sets/{alice_set}", headers=bob, json={"name": "偷看"}), 404)
    body(client.delete(f"/timetable/sets/{alice_set}", headers=bob), 404)
    assert _names(client, bob) == [] and _names(client, alice) == ["高等数学"]


def test_delete_set_switches_or_leaves_empty(client, auth):
    _course(client, auth)
    first = body(client.get("/timetable/sets", headers=auth))["active_id"]
    second = body(client.post("/timetable/sets", headers=auth, json={"name": "第二套"}))["sets"]["active_id"]
    _course(client, auth, course_name="大学英语")

    # 删除生效那套：自动切到剩下的
    data = body(client.delete(f"/timetable/sets/{second}", headers=auth))
    assert data["sets"]["active_id"] == first and [c["course_name"] for c in data["courses"]] == ["高等数学"]
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        assert db.query(Timetable).filter(Timetable.set_id == second).count() == 0
    finally:
        db.close()

    # 删掉最后一套：课表为空，再加课会重新建"我的课表"
    data = body(client.delete(f"/timetable/sets/{first}", headers=auth))
    assert data["courses"] == [] and data["sets"]["active_id"] is None
    _course(client, auth, course_name="线性代数")
    assert _names(client, auth) == ["线性代数"]
    body(client.delete("/timetable/sets/987654", headers=auth), 404)


def test_create_set_adopts_existing_courses_and_blank_settings(client, auth):
    _course(client, auth)
    # 不沿用设置：新课表用默认 20 周
    body(client.put("/timetable/settings", headers=auth, json={"total_weeks": 16}))
    data = body(client.post("/timetable/sets", headers=auth, json={"name": "空白", "copy_settings": False}))
    assert data["total_weeks"] == 20 and data["semester_start"] is None
    names = {s["name"]: s["course_count"] for s in data["sets"]["items"]}
    assert names == {"我的课表": 1, "空白": 0}
    # 只建不切换
    data = body(client.post("/timetable/sets", headers=auth, json={"name": "备用", "activate": False}))
    assert data["sets"]["active_name"] == "空白"


def test_import_commit_into_new_set(client, auth):
    _course(client, auth)
    payload = {"courses": [{"course_name": "数据库", "day_of_week": 4, "start_period": 1, "end_period": 2}],
               "semester": "2026-2027-1", "file_name": "大三上.pdf", "target": "new"}
    body(client.post("/import/timetable/commit", headers=auth, json=payload))
    data = body(client.get("/timetable", headers=auth))
    assert data["sets"]["active_name"] == "大三上" and data["semester"] == "2026-2027-1"
    assert [c["course_name"] for c in data["courses"]] == ["数据库"]
    # 同名再导一次自动加序号；导入到当前课表（replace）只清空当前那套
    body(client.post("/import/timetable/commit", headers=auth, json=payload))
    assert body(client.get("/timetable", headers=auth))["sets"]["active_name"] == "大三上 (2)"
    payload.update(target="current", courses=[{"course_name": "编译原理", "day_of_week": 5, "start_period": 3, "end_period": 4}])
    body(client.post("/import/timetable/commit", headers=auth, json=payload))
    assert _names(client, auth) == ["编译原理"]
    counts = {s["name"]: s["course_count"] for s in body(client.get("/timetable/sets", headers=auth))["items"]}
    assert counts == {"我的课表": 1, "大三上": 1, "大三上 (2)": 1}


def test_share_import_as_new_set(client, register):
    sharer, _ = register("小林")
    friend, _ = register("阿哲")
    start = timeutil.monday_of(timeutil.today()).isoformat()
    body(client.put("/timetable/settings", headers=sharer, json={"semester_start": start, "total_weeks": 16}))
    _course(client, sharer, course_name="体育", day_of_week=5)
    code = body(client.post("/timetable/share", headers=sharer))["code"]

    _course(client, friend)  # 朋友自己的课保持不动
    result = body(client.post(f"/timetable/share/{code}/import", headers=friend, json={"mode": "new"}))
    assert result["added_count"] == 1
    timetable = result["timetable"]
    assert timetable["sets"]["active_name"] == "小林的课表" and timetable["semester_start"] == start
    assert timetable["total_weeks"] == 16 and [c["course_name"] for c in timetable["courses"]] == ["体育"]
    counts = {s["name"]: s["course_count"] for s in timetable["sets"]["items"]}
    assert counts == {"我的课表": 1, "小林的课表": 1}


LEGACY_SQL = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50) UNIQUE, email VARCHAR(100) UNIQUE,
                    hashed_password VARCHAR(200), full_name VARCHAR(100), is_active BOOLEAN, semester VARCHAR(40),
                    total_weeks INTEGER, created_at DATETIME, updated_at DATETIME);
CREATE TABLE timetables (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), course_name VARCHAR(160),
                         day_of_week INTEGER, start_period INTEGER, end_period INTEGER, start_time VARCHAR(10),
                         end_time VARCHAR(10), semester VARCHAR(40), created_at DATETIME);
INSERT INTO users VALUES (1, 'a', 'a@example.com', 'x', 'A', 1, '2025-2026-2', 18, NULL, NULL);
INSERT INTO users VALUES (2, 'b', 'b@example.com', 'x', 'B', 1, '2025-2026-2', 20, NULL, NULL);
INSERT INTO users VALUES (3, 'c', 'c@example.com', 'x', 'C', 1, '2025-2026-2', 20, NULL, NULL);
INSERT INTO timetables VALUES (1, 1, '高等数学', 1, 1, 2, '08:00', '09:35', '2025-2026-2', NULL);
INSERT INTO timetables VALUES (2, 1, '线性代数', 2, 1, 2, '08:00', '09:35', '2025-2026-2', NULL);
INSERT INTO timetables VALUES (3, 1, '旧学期的课', 3, 1, 2, '08:00', '09:35', '2025-2026-1', NULL);
INSERT INTO timetables VALUES (4, 2, '只有旧学期', 3, 1, 2, '08:00', '09:35', '2024-2025-1', NULL);
"""


def test_migration_backfills_sets():
    path = Path(tempfile.mkdtemp()) / "legacy_sets.db"
    raw = sqlite3.connect(path)
    raw.executescript(LEGACY_SQL)
    raw.close()
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    sync_schema(engine)
    from app.services import schedule
    from app.models import User

    with Session(engine) as db:
        repair_data(db)
        repair_data(db)  # 可重复执行，不会重复建套
        a = db.get(User, 1)
        sets_a = {s.name: s for s in schedule.list_sets(db, a)}
        assert set(sets_a) == {"我的课表", "2025-2026-1"}
        assert sets_a["我的课表"].is_active and not sets_a["2025-2026-1"].is_active
        assert sets_a["我的课表"].total_weeks == 18
        # 升级后看到的课表与升级前一致：只有当前学期的两门
        assert sorted(c.course_name for c in schedule.user_courses(db, a)) == ["线性代数", "高等数学"]
        assert db.query(Timetable).filter(Timetable.set_id.is_(None)).count() == 0
        # 切到旧学期那套能看到旧课
        schedule.activate_set(db, a, sets_a["2025-2026-1"])
        assert [c.course_name for c in schedule.user_courses(db, a)] == ["旧学期的课"]
        assert a.semester == "2025-2026-1" and a.total_weeks == 18

        # 只有旧学期课程的用户：生效的是一套空的"我的课表"，显示与升级前一致（为空）
        b = db.get(User, 2)
        sets_b = {s.name: s for s in schedule.list_sets(db, b)}
        assert set(sets_b) == {"我的课表", "2024-2025-1"} and sets_b["我的课表"].is_active
        assert schedule.user_courses(db, b) == []
        # 没有课程的用户不建套
        assert schedule.list_sets(db, db.get(User, 3)) == []
    engine.dispose()
