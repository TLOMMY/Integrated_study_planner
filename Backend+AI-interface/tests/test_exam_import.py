"""
考试安排导入：本地解析（表格 / 复制的文字 / 网页 / 文字版 PDF）不调用模型；
解析不出来或是截图时交给模型（本地假响应）。预览可改、可勾选，同名同日的已有考试默认不勾、提交时跳过。
"""

import io
import json
from datetime import date, timedelta
from types import SimpleNamespace

from conftest import body
from test_import_ai import _provider, png_bytes
from test_llm import completion, fake_llm  # noqa: F401 - fake_llm 是夹具

from app.services import exam_import, schedule

TODAY = date(2026, 12, 20)


def _user(semester_start=None):
    return SimpleNamespace(semester_start=semester_start, period_times=None, total_weeks=20)


def _preview(client, headers, *, text=None, name=None, content=None, provider_id=None):
    data = {"text": text} if text is not None else {}
    if provider_id is not None:
        data["provider_id"] = str(provider_id)
    files = {"file": (name, content)} if name else None
    return client.post("/import/exams", headers=headers, data=data, files=files)


# ---------------------------------------------------------------- 日期与时间
def test_full_date_with_time_range():
    day, start, end, rest, problem = exam_import.parse_when("高等数学 2027-01-08 09:00-11:00 教一201", _user(), TODAY)
    assert (day, start, end, problem) == (date(2027, 1, 8), "09:00", "11:00", None)
    assert "高等数学" in rest and "教一201" in rest and "09" not in rest


def test_month_day_without_year_picks_the_next_one():
    day, start, end, _, _ = exam_import.parse_when("1月8日（周五）14:30～16:30", _user(), TODAY)
    assert (day, start, end) == (date(2027, 1, 8), "14:30", "16:30")
    # 两个月内已经过去的日子算今年（刚考完的），不跳到明年
    assert exam_import.parse_when("12月1日", _user(), TODAY)[0] == date(2026, 12, 1)


def test_week_and_weekday_use_semester_start():
    day, _, _, _, problem = exam_import.parse_when("第18周 星期三 第1-2节", _user("2026-09-07"), TODAY)
    assert day == date(2026, 9, 7) + timedelta(weeks=17, days=2) and problem is None
    day, _, _, _, problem = exam_import.parse_when("第18周星期三", _user(), TODAY)
    assert day is None and "开学日期" in problem


def test_periods_become_times():
    times = schedule.DEFAULT_PERIOD_TIMES
    _, start, end, _, _ = exam_import.parse_when("2027-01-08 第3-4节", _user(), TODAY)
    assert (start, end) == (times[2]["start"], times[3]["end"])


# ---------------------------------------------------------------- 复制的文字 / 表格
def test_pasted_lines():
    text = "考试安排\n高等数学A  2027-01-08 09:00-11:00  教一201  座位号 15\n大学英语  1月10日 14:00-16:00  B2203\n"
    items, _ = exam_import.parse_text(text, _user(), ["高等数学A", "大学英语"], TODAY)
    assert [i["title"] for i in items] == ["高等数学A", "大学英语"]
    first = items[0]
    assert (first["exam_date"], first["start_time"], first["end_time"]) == ("2027-01-08", "09:00", "11:00")
    assert first["location"] == "教一201" and "座位号 15" in first["note"] and first["subject"] == "高等数学A"
    assert items[1]["exam_date"] == "2027-01-10" and items[1]["location"] == "B2203"


def test_tab_separated_with_header():
    text = ("序号\t课程代码\t课程名称\t考试日期\t考试时间\t考试地点\t座位号\n"
            "1\tMATH101\t线性代数\t2027/1/12\t14:00-16:00\t教二 305\t8\n"
            "2\tCS201\t数据结构\t2027-01-14\t第1-2节\t机房 A\t\n")
    items, skipped = exam_import.parse_text(text, _user(), [], TODAY)
    assert [i["title"] for i in items] == ["线性代数", "数据结构"] and not skipped
    assert items[0]["exam_date"] == "2027-01-12" and items[0]["location"] == "教二 305" and items[0]["note"] == "座位号 8"
    assert items[1]["start_time"] == schedule.DEFAULT_PERIOD_TIMES[0]["start"]


# ---------------------------------------------------------------- 接口
def test_preview_commit_and_skip_duplicates(client, register, fake_llm):  # noqa: F811
    calls, _ = fake_llm
    headers, _ = register()
    soon = date.today() + timedelta(days=20)
    text = f"概率论  {soon.isoformat()} 09:00-11:00  教一 201\n离散数学  {(soon + timedelta(days=2)).isoformat()} 14:00"
    preview = body(_preview(client, headers, text=text))
    assert preview["source"] == "local" and preview["count"] == 2 and preview["selected_count"] == 2
    assert calls == [], "本地能解析时不调用模型"

    items = [{k: i[k] for k in ("title", "subject", "exam_date", "start_time", "end_time", "location", "note")}
             for i in preview["items"]]
    saved = body(client.post("/import/exams/commit", headers=headers, json={"items": items}))
    assert saved["created_count"] == 2 and saved["created"][0]["end_time"] == "11:00"

    # 再导一次：已有的标出来、默认不勾；硬提交也会跳过
    again = body(_preview(client, headers, text=text))
    assert again["duplicate_count"] == 2 and again["selected_count"] == 0
    saved = body(client.post("/import/exams/commit", headers=headers, json={"items": items}))
    assert saved["created_count"] == 0 and saved["skipped_count"] == 2
    exams = body(client.get("/exams", headers=headers))["upcoming"]
    assert [e["title"] for e in exams] == ["概率论", "离散数学"]


def test_xlsx_with_header(client, register):
    from openpyxl import Workbook

    headers, _ = register()
    soon = date.today() + timedelta(days=30)
    book = Workbook()
    sheet = book.active
    sheet.append(["课程名称", "考试日期", "考试时间", "考场"])
    sheet.append(["大学物理", soon, "08:30-10:30", "理科楼 101"])
    buffer = io.BytesIO()
    book.save(buffer)
    preview = body(_preview(client, headers, name="考试安排.xlsx", content=buffer.getvalue()))
    item = preview["items"][0]
    assert (item["title"], item["exam_date"], item["start_time"], item["location"]) == (
        "大学物理", soon.isoformat(), "08:30", "理科楼 101")


def test_saved_web_page(client, register):
    headers, _ = register()
    soon = (date.today() + timedelta(days=15)).isoformat()
    page = (f"<html><body><script>alert(1)</script><table><tr><th>课程</th><th>考试时间</th><th>地点</th></tr>"
            f"<tr><td>操作系统</td><td>{soon} 10:00-12:00</td><td>教三 402</td></tr></table></body></html>")
    preview = body(_preview(client, headers, name="考试.html", content=page.encode()))
    assert preview["items"][0]["title"] == "操作系统" and preview["items"][0]["location"] == "教三 402"


def test_screenshot_goes_to_vision_model(client, register, fake_llm):  # noqa: F811
    calls, queue = fake_llm
    headers, _ = register()
    _provider(client, headers, "qwen-vl-plus")
    soon = (date.today() + timedelta(days=10)).isoformat()
    queue.append(completion(json.dumps({"exams": [
        {"title": "高等数学", "date": soon, "start_time": "09:00", "end_time": "11:00", "location": "A101", "seat": "3"},
        {"title": "形势与政策", "week": 18, "weekday": 3},
    ]}, ensure_ascii=False)))
    preview = body(_preview(client, headers, name="考试.png", content=png_bytes()))
    assert preview["source"] == "ai" and preview["model"].endswith("qwen-vl-plus")
    assert any(p.get("type") == "image_url" for p in calls[-1]["body"]["messages"][1]["content"])
    first, second = preview["items"]
    assert first["note"] == "座位号 3" and first["selected"]
    # 没设开学日期：第 18 周换算不出日期，留给同学手动选，不默认勾选
    assert second["exam_date"] == "" and not second["selected"] and "开学日期" in second["problem"]


def test_unparseable_text_without_model(client, register):
    headers, _ = register()
    assert body(_preview(client, headers, text="明天记得带准考证"), 422)["reason"] == "no_model"
    assert body(_preview(client, headers, text="   "), 422) is None
