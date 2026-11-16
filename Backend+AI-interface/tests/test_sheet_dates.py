"""
表格日期 / 时间的读法（考试安排、课表导入共用 sheet_reader），以及文字版 PDF 课表按表格线本地解析。
不调用模型、不访问外网。
"""

import io
from datetime import date, datetime, time
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import body
from openpyxl import Workbook

from app.services import exam_import, importer, sheet_reader

TODAY = date(2026, 11, 12)
SAMPLE = Path(__file__).resolve().parents[2] / "data-import" / "25卓越人才4班课表.xls"


def _user():
    return SimpleNamespace(semester_start="2026-09-07", period_times=None, total_weeks=20)


def _xlsx(rows, merges=(), formats=None):
    book = Workbook()
    sheet = book.active
    for row in rows:
        sheet.append(row)
    for area in merges:
        sheet.merge_cells(area)
    for cell, number_format in (formats or {}).items():
        sheet[cell].number_format = number_format
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _parse(content):
    rows = exam_import._read_table("考试.xlsx", content)
    items, _ = exam_import.parse_rows(rows, _user(), [], TODAY)
    return [(i["title"], i["exam_date"], i["start_time"], i["end_time"]) for i in items]


# ---------------------------------------------------------------- 考试表：各种日期 / 时间写法
def test_date_and_time_cells():
    content = _xlsx([["课程名称", "考试日期", "开始时间", "结束时间"],
                     ["数据结构", date(2027, 1, 8), time(9, 0), time(11, 0)]])
    assert _parse(content) == [("数据结构", "2027-01-08", "09:00", "11:00")]


def test_excel_serial_and_time_fraction():
    """日期单元格没设日期格式（读出来是序列号 46395），时间是一天的小数。"""
    content = _xlsx([["课程名称", "考试日期", "开始时间", "结束时间"],
                     ["数据结构", 46395, 0.375, 0.4583333333]])
    assert _parse(content) == [("数据结构", "2027-01-08", "09:00", "11:00")]


def test_merged_date_cell_covers_following_rows():
    content = _xlsx([["考试日期", "考试时间", "课程名称"],
                     [date(2027, 1, 8), "09:00-11:00", "数据结构"],
                     [None, "14:00-16:00", "高等数学"],
                     [date(2027, 1, 10), "09:00-11:00", "大学英语"]], merges=["A2:A3"])
    assert [i[1] for i in _parse(content)] == ["2027-01-08", "2027-01-08", "2027-01-10"]


def test_week_and_weekday_columns():
    content = _xlsx([["课程名称", "周次", "星期", "开始时间", "结束时间"],
                     ["数据结构", 18, "星期五", time(14, 0), time(16, 0)]])
    # 开学 2026-09-07（周一）→ 第 18 周周五 = 2027-01-08
    assert _parse(content) == [("数据结构", "2027-01-08", "14:00", "16:00")]


@pytest.mark.parametrize("text, expected", [
    ("2027.1.8 下午2:30-4:30", ("2027-01-08", "14:30", "16:30")),
    ("01/08/2027 9:00-11:00", ("2027-01-08", "09:00", "11:00")),
    ("２０２７年１月８日　１４：００－１６：００", ("2027-01-08", "14:00", "16:00")),
    ("2027年1月8日(星期五) 第1-2节", ("2027-01-08", "08:00", "09:35")),
])
def test_text_formats(text, expected):
    day, start, end, _, _ = exam_import.parse_when(text, _user(), TODAY)
    assert (day.isoformat(), start, end) == expected


def test_repeated_header_rows_are_skipped():
    content = _xlsx([["课程名称", "考试日期"], ["数据结构", "2027-01-08"], ["课程名称", "考试日期"], ["高等数学", "2027-01-10"]])
    assert [i[0] for i in _parse(content)] == ["数据结构", "高等数学"]


def test_model_date_is_checked_against_source():
    items = [exam_import.make_item("数据结构", date(2027, 8, 1), "09:00", None)]
    exam_import._check_dates(items, "数据结构  2027-01-08  09:00-11:00  教一201", _user(), TODAY)
    assert items[0]["exam_date"] == "2027-01-08" and "校正" in items[0]["problem"]


# ---------------------------------------------------------------- 课表：真实样本 .xls 与文字版 PDF
@pytest.mark.skipif(not SAMPLE.exists(), reason="没有样本课表")
def test_sample_xls_timetable():
    result = importer.parse_timetable(SAMPLE.name, SAMPLE.read_bytes(), _user())
    names = {c["course_name"] for c in result.courses}
    assert {"概率论与数理统计", "工科数学分析(二)", "基础物理(二)", "中国近现代史纲要"} <= names
    prob = [c for c in result.courses if c["course_name"] == "概率论与数理统计" and c["day_of_week"] == 1]
    assert prob and prob[0]["weeks"] == list(range(2, 17, 2)) and prob[0]["classroom"] == "A1409"


def _timetable_pdf() -> bytes:
    reportlab = pytest.importorskip("reportlab")  # noqa: F841
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    style = ParagraphStyle("c", fontName="STSong-Light", fontSize=7, leading=9)
    para = lambda t: Paragraph(t.replace("\n", "<br/>"), style)  # noqa: E731
    cells = {(1, 2): "概率论与数理统计\n◇2-16周(双)(1-2节)◇A1409◇刘卉灵",
             (1, 4): "基础物理(二)\n◇1-16周(1-2节)◇A1308◇黄晓东",
             (3, 3): "工科数学分析(二)\n◇1-17周(3-4节)◇A1408◇王友军"}
    data = [[para(h) for h in ["节次", "", "星期一", "星期二", "星期三"]]]
    for r in range(1, 5):
        data.append(["", para(str(r))] + [para(cells[(r, c)]) if (r, c) in cells else "" for c in range(2, 5)])
    table = Table(data, colWidths=[30, 30, 160, 160, 160])
    spans = [("SPAN", (c, r), (c, r + 1)) for (r, c) in cells]
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "black"), ("VALIGN", (0, 0), (-1, -1), "TOP"), *spans]))
    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=landscape(A4)).build([table])
    return buffer.getvalue()


def test_text_pdf_timetable_is_parsed_locally():
    pytest.importorskip("pdfplumber")
    result = importer.parse_pdf_table(_timetable_pdf(), _user())
    assert result is not None
    got = {(c["course_name"], c["day_of_week"], c["start_period"], c["end_period"]) for c in result.courses}
    assert got == {("概率论与数理统计", 1, 1, 2), ("基础物理(二)", 3, 1, 2), ("工科数学分析(二)", 2, 3, 4)}


def test_pdf_route_does_not_call_model(client, register, monkeypatch):
    pytest.importorskip("pdfplumber")
    from app.ai import vision

    def boom(*args, **kwargs):
        raise AssertionError("文字版 PDF 表格不应调用模型")

    monkeypatch.setattr(vision, "_call", boom)
    headers, _ = register()
    data = body(client.post("/import/timetable/ai", headers=headers, files={"file": ("课表.pdf", _timetable_pdf())}))
    assert data["format"] == "pdf-table" and data["success_count"] == 3


def test_datetime_formatting():
    assert sheet_reader.format_value(datetime(2027, 1, 8)) == "2027-01-08"
    assert sheet_reader.format_value(datetime(2027, 1, 8, 9, 30)) == "2027-01-08 09:30"
    assert sheet_reader.format_value(time(14, 5)) == "14:05"
    assert sheet_reader.format_value(3.0) == "3"
