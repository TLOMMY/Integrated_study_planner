# -*- coding: utf-8 -*-
"""
读取 Excel / CSV 表格（课表导入、考试安排导入、AI 附件共用）。

教务系统导出的表格有几个坑，这里统一处理：
  · .xls 里的日期 / 时间单元格存的是 Excel 序列号（46395 = 2027-01-08，0.375 = 09:00），要按单元格类型换成文字；
  · .xlsx 设了日期格式的单元格由 openpyxl 读成 datetime，这里统一格式（日期 YYYY-MM-DD、时间 HH:MM、零点不写时间）；
  · 合并单元格只有左上角有值：返回合并区域，考试表需要把值填到区域里的每一格（同一天的几场考试共用一个日期格）。
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import List, Tuple

from app.core.errors import ApiError

SUPPORTED_SUFFIXES = {".xls", ".xlsx", ".csv"}
MAX_ROWS = 3000
MAX_COLS = 60


@dataclass
class Sheet:
    rows: List[List[str]] = field(default_factory=list)
    # 合并区域 (首行, 首列, 末行, 末列)，下标从 0 开始、含首尾
    merges: List[Tuple[int, int, int, int]] = field(default_factory=list)


def _clean(value) -> str:
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def format_value(value) -> str:
    """Python 值 → 单元格文字。日期只留日期，零点的 datetime 不写时间；整数的浮点数去掉 .0。"""
    if value is None:
        return ""
    if isinstance(value, datetime):
        if (value.hour, value.minute, value.second) == (0, 0, 0):
            return value.date().isoformat()
        if value.year < 1901:  # 只有时间的单元格偶尔读成 1899-12-30 hh:mm
            return value.strftime("%H:%M")
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, timedelta):
        minutes = int(value.total_seconds() // 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _clean(value)


def _xls(content: bytes) -> Sheet:
    import xlrd

    try:
        book = xlrd.open_workbook(file_contents=content, formatting_info=True)
    except (xlrd.biffh.XLRDError, NotImplementedError):
        # 个别导出工具写的 .xls 不带格式信息：读不到合并区域，值照常读
        book = xlrd.open_workbook(file_contents=content)
    sheet = book.sheet_by_index(0)

    def text(r: int, c: int) -> str:
        kind, value = sheet.cell_type(r, c), sheet.cell_value(r, c)
        if kind == xlrd.XL_CELL_DATE:
            try:
                y, m, d, hh, mm, ss = xlrd.xldate_as_tuple(value, book.datemode)
            except (xlrd.xldate.XLDateError, ValueError):
                return format_value(value)
            if (y, m, d) == (0, 0, 0):
                return f"{hh:02d}:{mm:02d}"
            if (hh, mm, ss) == (0, 0, 0):
                return f"{y:04d}-{m:02d}-{d:02d}"
            return f"{y:04d}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}"
        if kind == xlrd.XL_CELL_BOOLEAN:
            return "是" if value else "否"
        if kind == xlrd.XL_CELL_ERROR:
            return ""
        return format_value(value)

    rows = [[text(r, c) for c in range(min(sheet.ncols, MAX_COLS))] for r in range(min(sheet.nrows, MAX_ROWS))]
    merges = [(r1, c1, r2 - 1, c2 - 1) for r1, r2, c1, c2 in (getattr(sheet, "merged_cells", None) or [])]
    return Sheet(rows, merges)


def _xlsx(content: bytes) -> Sheet:
    from openpyxl import load_workbook

    # 不用 read_only：只读模式拿不到合并区域；文件已限制在 5MB 内
    book = load_workbook(io.BytesIO(content), data_only=True)
    sheet = book.worksheets[0]
    rows = []
    for index, row in enumerate(sheet.iter_rows(values_only=True)):
        if index >= MAX_ROWS:
            break
        rows.append([format_value(v) for v in row[:MAX_COLS]])
    merges = [(m.min_row - 1, m.min_col - 1, m.max_row - 1, m.max_col - 1) for m in sheet.merged_cells.ranges]
    return Sheet(rows, merges)


def _csv(content: bytes) -> Sheet:
    for encoding in ("utf-8-sig", "gbk"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ApiError(422, "CSV 文件编码无法识别，请另存为 UTF-8")
    rows = [[_clean(v) for v in row][:MAX_COLS] for row in csv.reader(io.StringIO(text))]
    return Sheet(rows[:MAX_ROWS])


def read_sheet(filename: str, content: bytes) -> Sheet:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ApiError(415, "暂只支持 .xls / .xlsx / .csv 课表文件（可从教务系统导出 Excel）")
    try:
        if suffix == ".xls":
            return _xls(content)
        if suffix == ".xlsx":
            return _xlsx(content)
        return _csv(content)
    except ApiError:
        raise
    except Exception as error:  # noqa: BLE001 - 第三方解析库异常类型各异
        raise ApiError(422, f"文件无法解析，请确认是教务系统导出的原始课表（{type(error).__name__}）") from None


def filled(sheet: Sheet) -> List[List[str]]:
    """把合并单元格的值填到区域里的每一格（考试表：同一天几场考试共用一个日期格）。"""
    rows = [list(row) for row in sheet.rows]
    for r1, c1, r2, c2 in sheet.merges:
        if r1 >= len(rows) or c1 >= len(rows[r1]):
            continue
        value = rows[r1][c1]
        for r in range(r1, min(r2, len(rows) - 1) + 1):
            for c in range(c1, c2 + 1):
                if c < len(rows[r]) and not rows[r][c]:
                    rows[r][c] = value
    return rows
