import io
from datetime import timedelta
from pathlib import Path

import pytest
from conftest import body

from app.core import timeutil
from app.services.schedule import format_weeks, parse_week_text

REAL_XLS = Path(__file__).resolve().parents[2] / "data-import" / "25卓越人才4班课表.xls"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2-16周(双)", list(range(2, 17, 2))),
        ("9-17周(单)", list(range(9, 18, 2))),
        ("1-3周,18周", [1, 2, 3, 18]),
        ("14周", [14]),
        ("1-16", list(range(1, 17))),
    ],
)
def test_parse_week_text(text, expected):
    assert parse_week_text(text, 22) == expected


def test_format_weeks_round_trip():
    assert format_weeks([2, 4, 6, 8]) == "2-8周(双)"
    assert format_weeks([1, 2, 3, 18]) == "1-3,18周"
    assert parse_week_text(format_weeks([1, 3, 5, 7]), 20) == [1, 3, 5, 7]


def _course(client, headers, **fields):
    payload = {"course_name": "高等数学", "day_of_week": 1, "start_period": 1, "end_period": 2, **fields}
    return client.post("/timetable", headers=headers, json=payload)


def test_conflict_detection_respects_weeks(client, auth):
    body(_course(client, auth, week_text="1-16周(单)"))
    clash = _course(client, auth, course_name="线性代数", week_text="1-5周")
    data = body(clash, 409)
    assert "高等数学" in clash.json()["message"] and data["conflicts"][0]["overlap_weeks"]
    # 单双周错开不算冲突
    body(_course(client, auth, course_name="大学物理", week_text="2-16周(双)"))
    # 确认后强制保存
    body(_course(client, auth, course_name="线性代数", week_text="1-5周", force=True))


def test_period_validation(client, auth):
    body(_course(client, auth, start_period=3, end_period=2), 422)
    body(_course(client, auth, start_period=1, end_period=14), 422)


def test_teaching_week_and_day_timeline(client, auth):
    today = timeutil.today()
    start = timeutil.monday_of(today) - timedelta(weeks=2)
    data = body(client.put("/timetable/settings", headers=auth, json={"semester_start": start.isoformat(), "total_weeks": 18}))
    assert data["current_week"] == 3 and data["week"] == 3
    weekday = today.isoweekday()
    body(_course(client, auth, course_name="本周有课", day_of_week=weekday, start_period=9, end_period=10, weeks=[3]))
    body(_course(client, auth, course_name="本周没课", day_of_week=weekday, start_period=1, end_period=2, weeks=[4]))
    timeline = body(client.get(f"/day/timeline?date={today.isoformat()}", headers=auth))
    titles = {item["title"] for item in timeline["items"] if item["type"] == "course"}
    assert titles == {"本周有课"} and timeline["teaching_week"] == 3
    week4 = body(client.get("/timetable?week=4", headers=auth))
    flags = {c["course_name"]: c["in_week"] for c in week4["courses"]}
    assert flags == {"本周有课": False, "本周没课": True}


def test_period_times_update_shifts_courses(client, auth):
    course = body(_course(client, auth))
    periods = [{"start": f"{7 + i:02d}:00", "end": f"{7 + i:02d}:45"} for i in range(12)]
    body(client.put("/timetable/settings", headers=auth, json={"period_times": periods}))
    updated = next(c for c in body(client.get("/timetable", headers=auth))["courses"] if c["id"] == course["id"])
    assert (updated["start_time"], updated["end_time"]) == ("07:00", "08:45")
    body(client.put("/timetable/settings", headers=auth, json={"period_times": periods[:2]}), 422)


def _upload(client, headers, name, content, mode="preview"):
    return client.post(f"/import/timetable?mode={mode}", headers=headers, files={"file": (name, content)})


def test_import_rejects_unsupported(client, auth):
    body(_upload(client, auth, "课表.pdf", b"%PDF-1.4"), 415)
    body(_upload(client, auth, "课表.xlsx", b"not a workbook"), 422)


def test_import_synthetic_grid_xlsx(client, auth):
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.append(["2025-2026学年第1学期"])
    sheet.append(["时间段", "节次", "星期一", "星期二", "星期三"])
    sheet.append(["上午", 1, "高等数学\n◇1-16周(1-2节)◇A101◇王老师◇  教学班：x", None,
                  "大学英语\n◇2-16周(双)(1-2节)◇B201◇李老师◇\n体育(板块)"])
    sheet.append(["", 3, None, "C++ 程序设计\n◇1-8周(3-4节)◇机房◇郭老师◇", None])
    sheet.append(["注：本学期2025-09-01正式上课至2026-01-18结束，共20周."])
    buffer = io.BytesIO()
    book.save(buffer)

    preview = body(_upload(client, auth, "grid.xlsx", buffer.getvalue()))
    assert preview["semester"] == "2025-2026-1" and preview["semester_start"] == "2025-09-01"
    assert preview["total_weeks"] == 20 and preview["success_count"] == 3
    assert preview["skipped"][0]["name"] == "体育(板块)"
    english = next(c for c in preview["courses"] if c["course_name"] == "大学英语")
    assert english["day_of_week"] == 3 and english["weeks"] == list(range(2, 17, 2))
    assert body(client.get("/timetable", headers=auth))["courses"] == []  # 预览不写库

    committed = body(_upload(client, auth, "grid.xlsx", buffer.getvalue(), mode="commit"))
    assert "importer" in {a["code"] for a in committed["reward"]["new_achievements"]}
    table = body(client.get("/timetable", headers=auth))
    assert table["semester"] == "2025-2026-1" and len(table["courses"]) == 3


def test_import_flat_csv(client, auth):
    csv_text = "课程,星期,节次,周次,教师,教室\n线性代数,周二,3-4,1-12周,陈老师,A202\n概率论,4,5-6,,刘老师,A303\n"
    data = body(_upload(client, auth, "flat.csv", csv_text.encode("gbk")))
    assert data["format"] == "table" and data["success_count"] == 2
    assert data["courses"][1]["weeks"] == list(range(1, 21))


@pytest.mark.skipif(not REAL_XLS.exists(), reason="本地真实课表文件不存在")
def test_import_real_zhengfang_xls(client, auth):
    data = body(_upload(client, auth, REAL_XLS.name, REAL_XLS.read_bytes()))
    assert data["semester"] == "2025-2026-2"
    assert data["semester_start"] == "2026-03-02" and data["total_weeks"] == 22
    assert data["success_count"] >= 20
    prob = next(c for c in data["courses"] if c["course_name"] == "概率论与数理统计" and c["day_of_week"] == 1)
    assert prob["weeks"] == list(range(2, 17, 2)) and prob["start_period"] == 1 and prob["classroom"] == "A1409"
    split = next(c for c in data["courses"] if c["course_name"] == "电子信息创新实践导论" and c["day_of_week"] == 4)
    assert split["weeks"] == [1, 2, 3, 18]
    assert any("板块" in s["name"] for s in data["skipped"])

    # 班级课表里列出了所有选修方向，只导入勾选的课程
    chosen = [i for i, c in enumerate(data["courses"]) if not c["course_name"].startswith("百步梯")]
    response = client.post("/import/timetable?mode=commit", headers=auth,
                           files={"file": (REAL_XLS.name, REAL_XLS.read_bytes())},
                           data={"selected": ",".join(map(str, chosen))})
    assert body(response)["success_count"] == len(chosen)
    table = body(client.get("/timetable", headers=auth))
    assert table["semester_start"] == "2026-03-02" and len(table["courses"]) == len(chosen)
