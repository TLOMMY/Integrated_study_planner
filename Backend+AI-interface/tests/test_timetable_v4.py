"""v4 · D：课表分享码（生成 / 预览 / 过期 / 导入冲突 / 覆盖本学期）。"""

from datetime import timedelta

from conftest import body

from app.core import timeutil
from app.core.database import SessionLocal
from app.models import TimetableShare


def _course(client, headers, **fields):
    payload = {"course_name": "高等数学", "day_of_week": 1, "start_period": 1, "end_period": 2, **fields}
    return body(client.post("/timetable", headers=headers, json=payload))


def test_share_requires_courses(client, auth):
    body(client.post("/timetable/share", headers=auth), 422)


def test_share_preview_and_import_with_conflicts(client, register):
    sharer, sharer_user = register("小林")
    friend, _ = register("阿哲")
    start = timeutil.monday_of(timeutil.today()).isoformat()
    body(client.put("/timetable/settings", headers=sharer, json={"semester_start": start, "total_weeks": 18}))
    _course(client, sharer, classroom="A1408", week_text="1-16周")
    _course(client, sharer, course_name="大学英语", day_of_week=2, start_period=3, end_period=4, week_text="1-16周")
    _course(client, sharer, course_name="体育", day_of_week=5, start_period=7, end_period=8, week_text="1-16周")

    share = body(client.post("/timetable/share", headers=sharer))
    code = share["code"]
    assert len(code) == 8 and code.isalnum() and code.upper() == code
    assert share["course_count"] == 3 and share["is_mine"] is True and share["owner_name"] == "小林"

    preview = body(client.get(f"/timetable/share/{code.lower()}", headers=friend))
    assert preview["is_mine"] is False and preview["owner_name"] == "小林"
    assert {c["course_name"] for c in preview["courses"]} == {"高等数学", "大学英语", "体育"}
    assert "id" not in preview["courses"][0]
    body(client.get("/timetable/share/NOPE2345", headers=friend), 404)

    # 朋友已有：同一时间的另一门课（冲突）+ 完全相同的高数（重复）
    _course(client, friend, week_text="1-16周")
    _course(client, friend, course_name="线性代数", day_of_week=2, start_period=3, end_period=4, week_text="1-8周")
    result = body(client.post(f"/timetable/share/{code}/import", headers=friend, json={"mode": "merge"}))
    assert result["added_count"] == 1 and [a["course_name"] for a in result["added"]] == ["体育"]
    reasons = {s["course_name"]: s["reason"] for s in result["skipped"]}
    assert "已有" in reasons["高等数学"] and "线性代数" in reasons["大学英语"]
    # 朋友原本没设开学日期，顺带用上分享者的
    assert result["timetable"]["semester_start"] == start
    assert len(result["timetable"]["courses"]) == 3

    # 覆盖本学期：原有课程清空，按分享者课表导入
    replaced = body(client.post(f"/timetable/share/{code}/import", headers=friend, json={"mode": "replace"}))
    assert replaced["added_count"] == 3 and replaced["skipped_count"] == 0
    names = sorted(c["course_name"] for c in body(client.get("/timetable", headers=friend))["courses"])
    assert names == ["体育", "大学英语", "高等数学"]

    # 分享者的课表不受影响
    assert len(body(client.get("/timetable", headers=sharer))["courses"]) == 3
    db = SessionLocal()
    try:
        row = db.query(TimetableShare).filter(TimetableShare.code == code).first()
        assert row.import_count == 2 and row.user_id == sharer_user["id"]
    finally:
        db.close()


def test_share_expires(client, register):
    sharer, _ = register()
    friend, _ = register()
    _course(client, sharer)
    code = body(client.post("/timetable/share", headers=sharer))["code"]
    db = SessionLocal()
    try:
        row = db.query(TimetableShare).filter(TimetableShare.code == code).first()
        assert (row.expires_at - timeutil.now()).days in (6, 7)
        row.expires_at = timeutil.now() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    body(client.get(f"/timetable/share/{code}", headers=friend), 410)
    body(client.post(f"/timetable/share/{code}/import", headers=friend, json={}), 410)


def test_share_import_respects_period_table(client, register):
    sharer, _ = register()
    friend, _ = register()
    _course(client, sharer, course_name="晚课", start_period=11, end_period=12)
    code = body(client.post("/timetable/share", headers=sharer))["code"]
    periods = [{"start": f"{8 + i:02d}:00", "end": f"{8 + i:02d}:45"} for i in range(8)]
    body(client.put("/timetable/settings", headers=friend, json={"period_times": periods}))
    result = body(client.post(f"/timetable/share/{code}/import", headers=friend, json={}))
    assert result["added_count"] == 0 and "8 节" in result["skipped"][0]["reason"]
    # 选择同时采用分享者的节次时间后即可导入
    result = body(client.post(f"/timetable/share/{code}/import", headers=friend, json={"use_period_times": True}))
    assert result["added_count"] == 1
    assert len(body(client.get("/timetable", headers=friend))["period_times"]) == 12
