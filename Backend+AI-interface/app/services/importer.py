# -*- coding: utf-8 -*-
"""
课表文件解析。

支持两种版式：
1. 正方教务"网格课表"：表头一行是 星期一…星期日，单元格内可能堆叠多门课，
   每门课形如 "课程名\\n◇2-16周(双)(1-2节)◇A1409◇教师◇ 教学班：…"。
   页脚 "本学期2026-03-02正式上课……共22周" 会被识别为开学日期与总周数。
2. 扁平表格：每行一门课，列名含 课程/星期/节次/周次/教师/教室（或 开始时间/结束时间）。

支持 .xls（xlrd）、.xlsx（openpyxl）、.csv。

网格单元格里没有 "◇" 时，按"课程块"解析（正方旧版网页、强智、青果等版式），
见 parse_blocks / group_lines；教务网页导入（import_web）也复用这一套。
"""

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.errors import ApiError
from app.services import schedule

WEEKDAY_MAP = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
_HEADER_DAY = re.compile(r"^(?:星期|周)([一二三四五六日天])$")
_SESSION = re.compile(r"^◇?\s*(?P<weeks>[^◇()（）]*?周(?:\s*[（(][单双][)）])?)\s*[（(](?P<p1>\d+)(?:-(?P<p2>\d+))?节[)）](?P<rest>.*)$")
_SEMESTER = re.compile(r"(\d{4})-(\d{4})学年第\s*([一二12])\s*学期")
_START = re.compile(r"(\d{4}-\d{2}-\d{2})\s*正式上课")
_TOTAL = re.compile(r"共\s*(\d+)\s*周")

SUPPORTED_SUFFIXES = {".xls", ".xlsx", ".csv"}


@dataclass
class ParseResult:
    format: str
    courses: List[dict] = field(default_factory=list)
    skipped: List[dict] = field(default_factory=list)
    semester: Optional[str] = None
    semester_start: Optional[str] = None
    total_weeks: Optional[int] = None


# ---------------------------------------------------------------- 读取
def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def _read_rows(filename: str, content: bytes) -> List[List[str]]:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ApiError(415, "暂只支持 .xls / .xlsx / .csv 课表文件（可从教务系统导出 Excel）")
    try:
        if suffix == ".xls":
            import xlrd

            book = xlrd.open_workbook(file_contents=content)
            sheet = book.sheet_by_index(0)
            return [[_cell_text(sheet.cell_value(r, c)) for c in range(sheet.ncols)] for r in range(sheet.nrows)]
        if suffix == ".xlsx":
            from openpyxl import load_workbook

            book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheet = book.worksheets[0]
            return [[_cell_text(v) for v in row] for row in sheet.iter_rows(values_only=True)]
        for encoding in ("utf-8-sig", "gbk"):
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ApiError(422, "CSV 文件编码无法识别，请另存为 UTF-8")
        return [[_cell_text(v) for v in row] for row in csv.reader(io.StringIO(text))]
    except ApiError:
        raise
    except Exception as error:  # noqa: BLE001 - 第三方解析库异常类型各异
        raise ApiError(422, f"文件无法解析，请确认是教务系统导出的原始课表（{type(error).__name__}）")


# ---------------------------------------------------------------- 元信息
def _detect_meta(rows: List[List[str]], result: ParseResult) -> None:
    for row in rows:
        for cell in row:
            if not cell:
                continue
            if result.semester is None and (m := _SEMESTER.search(cell)):
                term = "1" if m.group(3) in ("一", "1") else "2"
                result.semester = f"{m.group(1)}-{m.group(2)}-{term}"
            if result.semester_start is None and (m := _START.search(cell)):
                result.semester_start = m.group(1)
            if result.total_weeks is None and "学期" in cell and (m := _TOTAL.search(cell)):
                result.total_weeks = int(m.group(1))


# ---------------------------------------------------------------- 网格版式
def _find_day_header(rows: List[List[str]], max_rows: int = 10, first_line: bool = False):
    """找到含 ≥3 个"星期X/周X"的表头行。first_line=True 时只看单元格第一行（网页表头常带日期）。"""
    for index, row in enumerate(rows[:max_rows]):
        columns = {}
        for col, cell in enumerate(row):
            text = cell.split("\n")[0] if first_line else cell
            m = _HEADER_DAY.match(text.replace(" ", "").replace("　", ""))
            if m:
                columns[col] = WEEKDAY_MAP[m.group(1)]
        if len(columns) >= 3:
            return index, columns
    return None, {}


def clean_teacher(teacher: str) -> str:
    names = [n.strip() for n in re.split(r"[,，、/]", teacher or "") if n.strip()]
    if len(names) > 3:
        return ("、".join(names[:3]) + "等")[:120]
    return "、".join(names)[:120]


def clean_classroom(classroom: str) -> str:
    classroom = (classroom or "").strip()
    return "待定" if classroom in ("未排地点", "无", "未安排") else classroom[:80]


def _parse_rest(rest: str) -> Dict[str, str]:
    parts = [p.strip() for p in rest.split("◇")]
    parts = [p for p in parts if p and not p.startswith(("教学班", "选课人数", "学分"))]
    classroom = parts[0] if parts else ""
    teacher = parts[1] if len(parts) > 1 else ""
    return {"classroom": clean_classroom(classroom), "teacher": clean_teacher(teacher)}


# ---------------------------------------------------------------- 课程块版式（正方旧版 / 强智 / 青果 / 正方新版网页）
# 节次："第1,2节"、"[01-02节]"、"(1-2节)"、"[01-02-03小节]"、"1-2节"。前面不能是"周"之类，避免把"3节/周"当节次
_PERIOD = re.compile(r"第?\s*(\d{1,2}(?:\s*[-,，、~～]\s*\d{1,2})*)\s*小?节(?!课)")
# 周次："第1-16周"、"1-16(周)"、"2-16(双周)"、"1-8,10-16周(单)"、"{第2-16周|双周}"
_WEEKS = re.compile(
    r"第?\s*(\d{1,2}(?:\s*[-~～]\s*\d{1,2})?(?:\s*[,，、]\s*\d{1,2}(?:\s*[-~～]\s*\d{1,2})?)*)"
    r"\s*(?:[（(]\s*([单双])?\s*周\s*[)）]|周)"
    r"(?:\s*[（(|]?\s*([单双])周?\s*[)）]?)?"
)
_DAY_IN_TEXT = re.compile(r"(?:星期|周)([一二三四五六日天])")
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
           "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15, "十六": 16}
_NOISE = re.compile(r"^(?:教学班|考核方式|考查|考试|选课备注|课程学时|周学时|总学时|学分|教学班组成|选课人数|课程性质|上课人数|重修|学时)")
_KEYVALUE = re.compile(r"^([^:：]{1,6})[:：]\s*(.*)$")
_SEPARATOR = re.compile(r"^[-—_=─]{4,}$")


def label_for(key: str) -> Optional[str]:
    """把 title 属性或 "教师：" 这样的前缀映射成字段名；不认识的返回 None。"""
    key = (key or "").strip()
    if not key or len(key) > 12:
        return None
    if any(word in key for word in ("学时", "学分", "考核", "教学班", "备注", "人数", "性质", "组成")):
        return "other"
    if any(word in key for word in ("教师", "老师", "任课")):
        return "teacher"
    if any(word in key for word in ("教室", "地点", "场地")):
        return "room"
    if any(word in key for word in ("周次", "节次", "时间")):
        return "time"
    if key in ("课程", "课程名", "课程名称"):
        return "name"
    return None


def is_time_line(text: str) -> bool:
    return bool(_PERIOD.search(text) or _WEEKS.search(text))


def _period_range(text: str):
    """返回 ((起, 止), 匹配区间)；没有节次时返回 ((None, None), None)。"""
    m = _PERIOD.search(text)
    if not m:
        return (None, None), None
    numbers = [int(n) for n in re.findall(r"\d+", m.group(1))]
    return (min(numbers), max(numbers)), m.span()


def _week_text(text: str) -> Optional[str]:
    m = _WEEKS.search(text)
    if not m:
        return None
    spec = re.sub(r"\s+", "", m.group(1)).replace("~", "-").replace("～", "-")
    parity = m.group(2) or m.group(3)
    return f"{spec}周" + (f"({parity})" if parity else "")


def row_periods(cells: List[str]):
    """从行首的"节次"列推断这一行的节次范围：先找"1-2小节"，再找"第1节"/"1"/"第一大节"。"""
    lines = [line.strip() for cell in cells for line in (cell or "").split("\n") if line.strip()]
    for line in lines:
        m = re.search(r"(\d{1,2}(?:\s*[-,，、~]\s*\d{1,2})*)\s*小节", line)
        if m:
            numbers = [int(n) for n in re.findall(r"\d+", m.group(1))]
            return min(numbers), max(numbers)
    for line in lines:
        if re.search(r"\d{1,2}:\d{2}", line) and not re.search(r"节", line):
            continue
        m = re.fullmatch(r"第?\s*(\d{1,2})(?:\s*[-~]\s*(\d{1,2}))?\s*节?", line)
        if m:
            p1 = int(m.group(1))
            return p1, int(m.group(2) or p1)
        m = re.match(r"第?\s*(\d{1,2})(?:\s*[-~]\s*(\d{1,2}))?\s*节", line)
        if m:
            p1 = int(m.group(1))
            return p1, int(m.group(2) or p1)
        m = re.match(r"第?\s*([一二三四五六七八九十]{1,3})\s*(大)?节", line)
        if m and m.group(1) in _CN_NUM:
            n = _CN_NUM[m.group(1)]
            return (2 * n - 1, 2 * n) if m.group(2) else (n, n)
    return None


def group_lines(lines: List[Tuple[Optional[str], Optional[str]]]) -> List[dict]:
    """
    把单元格的行切成课程块。lines 为 (文本, 标签) 序列，文本为 None 表示分隔符（如 <hr>、新的课程 div），
    标签取 name/teacher/room/time/other 或 None（未标注，按位置猜测）。
    正方旧版：课程名 / 时间 / 教师 / 教室；强智：课程名 / 教师(title) / 周次(title) / 教室(title)；
    正方新版网页：课程名 / 节次周次(title) / 地点(title) / 教师(title)。
    """
    courses: List[dict] = []
    current: Optional[dict] = None

    def finish():
        nonlocal current
        if current and current["name"]:
            courses.append(current)
        current = None

    def new(name: str):
        nonlocal current
        finish()
        current = {"name": name, "teacher": "", "room": "", "times": [], "pre": [], "post": []}

    texts = list(lines)
    for index, (text, label) in enumerate(texts):
        if text is None or _SEPARATOR.match(text or ""):
            finish()
            continue
        text = text.strip()
        if not text:
            # 空行：一门课已有时间信息时作为分隔
            if current and current["times"]:
                finish()
            continue
        if label is None:
            kv = _KEYVALUE.match(text)
            if kv and label_for(kv.group(1)):
                label, text = label_for(kv.group(1)), kv.group(2).strip()
            elif _NOISE.match(text):
                label = "other"
        if label == "other" or not text:
            continue
        if label == "name":
            new(text)
            continue
        if label == "time" or (label is None and is_time_line(text) and current is not None):
            if current is None:
                continue
            if current["pre"] and not current["teacher"]:
                current["teacher"] = current["pre"].pop(0)
            current["times"].append(text)
            continue
        if label in ("teacher", "room"):
            if current is None:
                continue
            if current[label] and current["times"]:
                current[label] += "," + text
            else:
                current[label] = text
            continue
        # 未标注的普通文本
        if current is None:
            new(text)
            continue
        if not current["times"]:
            current["pre"].append(text)
            continue
        upcoming = next((t for t, lab in texts[index + 1:] if t and t.strip() and lab != "other"), None)
        if upcoming is not None and is_time_line(upcoming) and not _NOISE.match(text):
            new(text)
        elif not current["teacher"]:
            current["teacher"] = text
        elif not current["room"]:
            current["room"] = text
        else:
            new(text)
    finish()
    return courses


def parse_blocks(blocks: List[dict], day: int, fallback_periods, total_weeks: int, default_total: int,
                 result: ParseResult, seen: set) -> None:
    """把 group_lines 的结果转成标准课程；时间里没写节次时用行首节次 fallback_periods。"""
    for block in blocks:
        name = re.sub(r"[★☆◆◇●○▲△■□※]+$", "", block["name"]).strip()
        if not name:
            continue
        if not block["times"]:
            result.skipped.append({"name": name[:60], "reason": "缺少周次/节次信息（可能是板块课或体育课）"})
            continue
        teacher, room = clean_teacher(block["teacher"]), clean_classroom(block["room"])
        for text in block["times"]:
            (p1, p2), span = _period_range(text)
            rest = text[:span[0]] + " " + text[span[1]:] if span else text
            if p1 is None and fallback_periods:
                p1, p2 = fallback_periods
            if p1 is None:
                result.skipped.append({"name": name[:60], "reason": f"节次无法识别：{text[:40]}"})
                continue
            week_text = _week_text(rest)
            weeks = schedule.parse_week_text(week_text, total_weeks) if week_text else list(range(1, default_total + 1))
            if not weeks:
                result.skipped.append({"name": name[:60], "reason": f"周次无法识别：{text[:40]}"})
                continue
            course_day = day
            if day is None:
                m = _DAY_IN_TEXT.search(rest)
                if not m:
                    result.skipped.append({"name": name[:60], "reason": "星期无法识别"})
                    continue
                course_day = WEEKDAY_MAP[m.group(1)]
            key = (name, course_day, p1, p2, tuple(weeks))
            if key in seen:
                continue
            seen.add(key)
            result.courses.append({
                "course_name": name[:160], "day_of_week": course_day, "start_period": p1, "end_period": max(p1, p2),
                "weeks": weeks, "week_text": schedule.format_weeks(weeks), "teacher": teacher, "classroom": room,
            })


def _parse_cell(cell: str, day: int, total_weeks: int, result: ParseResult, seen: set,
                fallback_periods=None, default_total: int = 20) -> None:
    if "◇" not in cell:
        blocks = group_lines([(line, None) for line in cell.split("\n")])
        parse_blocks(blocks, day, fallback_periods, total_weeks, default_total, result, seen)
        return
    current_name = None
    has_session = False
    for raw in cell.split("\n"):
        line = raw.strip()
        if not line:
            continue
        session = _SESSION.match(line)
        if session is None:
            if current_name and not has_session:
                result.skipped.append({"name": current_name, "reason": "缺少周次/节次信息（可能是板块课或体育课）"})
            current_name, has_session = line, False
            continue
        if not current_name:
            continue
        has_session = True
        weeks = schedule.parse_week_text(session.group("weeks"), total_weeks)
        p1 = int(session.group("p1"))
        p2 = int(session.group("p2") or p1)
        if not weeks:
            result.skipped.append({"name": current_name, "reason": f"周次无法识别：{session.group('weeks')}"})
            continue
        key = (current_name, day, p1, p2, tuple(weeks))
        if key in seen:
            continue
        seen.add(key)
        result.courses.append(
            {
                "course_name": current_name[:160],
                "day_of_week": day,
                "start_period": p1,
                "end_period": p2,
                "weeks": weeks,
                "week_text": schedule.format_weeks(weeks),
                **_parse_rest(session.group("rest")),
            }
        )
    if current_name and not has_session:
        result.skipped.append({"name": current_name, "reason": "缺少周次/节次信息（可能是板块课或体育课）"})


def _parse_grid(rows: List[List[str]], header_index: int, day_columns: Dict[int, int], result: ParseResult,
                default_total: int = 20) -> None:
    total = result.total_weeks or 30
    seen: set = set()
    first_day = min(day_columns)
    for row in rows[header_index + 1:]:
        fallback = row_periods(row[:first_day])
        for col, day in day_columns.items():
            if col < len(row) and row[col]:
                _parse_cell(row[col], day, total, result, seen, fallback, default_total)


# ---------------------------------------------------------------- 扁平版式
_FLAT_COLUMNS = {
    "course_name": ("课程", "课程名", "课程名称", "course", "course_name", "name"),
    "day": ("星期", "周几", "上课星期", "day", "day_of_week", "weekday"),
    "periods": ("节次", "上课节次", "period", "periods"),
    "weeks": ("周次", "上课周次", "weeks"),
    "teacher": ("教师", "老师", "任课教师", "teacher"),
    "classroom": ("教室", "地点", "上课地点", "classroom", "location"),
    "start_time": ("开始时间", "开始", "start_time"),
    "end_time": ("结束时间", "结束", "end_time"),
}


def _parse_day(value: str) -> Optional[int]:
    for char, number in WEEKDAY_MAP.items():
        if char in value:
            return number
    m = re.search(r"[1-7]", value)
    return int(m.group(0)) if m else None


def _parse_flat(rows: List[List[str]], user, result: ParseResult) -> bool:
    for index, row in enumerate(rows[:10]):
        normalized = [cell.strip().lower() for cell in row]
        mapping = {}
        for key, names in _FLAT_COLUMNS.items():
            for col, cell in enumerate(normalized):
                if cell in names:
                    mapping[key] = col
                    break
        if "course_name" in mapping and "day" in mapping:
            break
    else:
        return False

    result.format = "table"
    total = result.total_weeks or int(user.total_weeks or 20)
    for row in rows[index + 1:]:
        get = lambda key: row[mapping[key]].strip() if key in mapping and mapping[key] < len(row) else ""  # noqa: E731
        name = get("course_name")
        if not name:
            continue
        day = _parse_day(get("day"))
        if day is None:
            result.skipped.append({"name": name, "reason": "星期无法识别"})
            continue
        period_match = re.search(r"(\d+)\s*(?:-\s*(\d+))?", get("periods"))
        if period_match:
            p1 = int(period_match.group(1))
            p2 = int(period_match.group(2) or p1)
        elif re.match(r"\d{1,2}:\d{2}", get("start_time")):
            p1 = schedule.time_to_period(user, get("start_time"))
            p2 = schedule.time_to_period(user, get("end_time") or get("start_time"), use_end=True)
        else:
            result.skipped.append({"name": name, "reason": "缺少节次或上课时间"})
            continue
        weeks = schedule.parse_week_text(get("weeks"), total) if get("weeks") else list(range(1, total + 1))
        if not weeks:
            result.skipped.append({"name": name, "reason": f"周次无法识别：{get('weeks')}"})
            continue
        result.courses.append(
            {
                "course_name": name[:160],
                "day_of_week": day,
                "start_period": p1,
                "end_period": max(p1, p2),
                "weeks": weeks,
                "week_text": schedule.format_weeks(weeks),
                "teacher": get("teacher")[:120],
                "classroom": get("classroom")[:80],
            }
        )
    return True


# ---------------------------------------------------------------- 入口
def parse_timetable(filename: str, content: bytes, user) -> ParseResult:
    rows = _read_rows(filename, content)
    result = ParseResult(format="grid")
    _detect_meta(rows, result)

    header_index, day_columns = _find_day_header(rows)
    if header_index is not None:
        _parse_grid(rows, header_index, day_columns, result, result.total_weeks or int(user.total_weeks or 20))
    elif not _parse_flat(rows, user, result):
        raise ApiError(422, "没有识别到课表结构：需要包含“星期一…星期日”表头，或“课程/星期/节次”列")

    if not result.courses:
        raise ApiError(422, "文件里没有解析出任何课程", {"skipped": result.skipped})
    return result
