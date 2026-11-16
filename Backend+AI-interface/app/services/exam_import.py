# -*- coding: utf-8 -*-
"""
考试安排导入：教务系统导出的表格（.xlsx / .xls / .csv）、保存的网页（.html）、复制的文字、截图 / PDF。

流程与课表导入一致：先预览（每条可改、可取消勾选，已有的同名同日考试默认不勾），确认后再写库。
  · 表格 / 网页 / 文字 / 文字版 PDF：先按表头和常见写法在本地解析，不调用模型、不占 AI 次数；
  · 本地解析不出来，或是图片 / 扫描件：交给大模型识别（与课表识别同一套模型和额度）。
日期只写了"1月8日"时补成最近的一次（不早于两个月前）；写成"第18周 星期三"时按开学日期换算。
"""

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core import timeutil
from app.core.errors import ApiError
from app.models import Exam, User
from app.services import schedule

MAX_ITEMS = 100
MAX_TEXT = 20000
MODEL_TEXT = 12000
TABLE_SUFFIXES = {".xlsx", ".xls", ".csv"}
HTML_SUFFIXES = {".html", ".htm"}
TEXT_SUFFIXES = {".txt", ".md"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
SUPPORTED = "表格（.xlsx / .xls / .csv）、网页（.html）、文字（.txt）、PDF 或截图"

WEEKDAYS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7,
            "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7}

_FULL_DATE = re.compile(r"(?<!\d)(20\d{2})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})\s*[日号]?")
# 月/日/年（Excel 美式区域导出的文字）：01/08/2027
_US_DATE = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})/(20\d{2})(?!\d)")
# 只有一个数字的单元格：Excel 日期序列号（2020-2040 年之间）
_SERIAL = re.compile(r"^\s*(4[3-9]\d{3}|5[0-1]\d{3})(?:\.\d+)?\s*$")
# 上午 / 下午 / 晚上 + 12 小时制时间
_AMPM = re.compile(r"(上午|早上|中午|下午|晚上|AM|PM|am|pm)\s*(\d{1,2})\s*[:：点]\s*(\d{1,2})?")
_MD_CN = re.compile(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?")
_MD_SLASH = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])")
_WEEK_DAY = re.compile(r"第\s*(\d{1,2})\s*(?:教学)?周\s*[,，、]?\s*(?:星期|周|礼拜)\s*([一二三四五六日天1-7])")
_TIME = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*[:：]\s*([0-5]\d)(?::\d{2})?"
                   r"(?:\s*[-~～—–至到]+\s*([01]?\d|2[0-3])\s*[:：]\s*([0-5]\d))?")
_PERIODS = re.compile(r"第?\s*(\d{1,2})\s*(?:[-~～—–至到]\s*(\d{1,2}))?\s*节")
_WEEKDAY_WORD = re.compile(r"[（(]?\s*(?:星期|周|礼拜)[一二三四五六日天][）)]?")
_SEAT = re.compile(r"(?:座位号?|座号)\s*[:：]?\s*([A-Za-z0-9-]{1,10})")
_PLACE = re.compile(r"(?:考试地点|地点|考场|考试教室|教室)\s*[:：]\s*(\S{1,40})")
_LABEL = re.compile(r"^(?:课程(?:名称)?|科目|考试(?:科目|名称|时间|日期)?|日期|时间)\s*[:：]\s*")
# 行内的"字段名："：换成空白当分隔，只留后面的值
_LABEL_ANY = re.compile(r"(?:课程名称|考试科目|考试名称|考试时间|考试日期|课程|科目|时间|日期|考试)\s*[:：]")
_SPLIT = re.compile(r"[\t|,，;；、]+|\s{2,}")
_PLACE_LIKE = re.compile(r"\d|[楼馆室教区厅]")

# 表头：每个字段的关键词（按顺序匹配）；含 IGNORE 里的词的列不算（如"课程号""任课教师"）
HEADERS = (
    ("start", ("开始时间", "开考时间", "起始时间", "开始")),
    ("end", ("结束时间", "终止时间", "截止时间", "结束")),
    ("date", ("考试日期", "日期")),
    ("week", ("考试周次", "教学周", "周次")),
    ("weekday", ("星期", "周几")),
    ("time", ("考试时间", "时间", "时段", "节次", "场次")),
    ("location", ("考试地点", "考试教室", "地点", "考场", "教室")),
    ("seat", ("座位号", "座位", "座号")),
    ("note", ("考试方式", "考核方式", "备注", "方式")),
    # 考试班级：同一张表里常列着全年级 / 全学院的考试，按班级筛出自己的
    ("classes", ("考试班级", "上课班级", "行政班", "教学班", "班级")),
    ("title", ("课程名称", "考试科目", "考试名称", "科目", "课程", "名称")),
)
IGNORE = ("代码", "编号", "课程号", "学分", "教师", "人数", "学号", "姓名", "序号")
# ---------------------------------------------------------------- 日期与时间
def _year_for(month: int, day: int, today: date) -> Optional[date]:
    """只写了月日：取离今天最近、且不早于两个月前的那一年（考试安排一般是接下来的）。"""
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate >= today - timedelta(days=60):
            return candidate
    return None


def _week_date(user: User, week: int, weekday: int) -> Optional[date]:
    if timeutil.parse_date(user.semester_start) is None or not 1 <= week <= 30:
        return None
    return schedule.week_dates(user, week)[weekday - 1]


def _serial_date(text: str) -> Optional[date]:
    """Excel 日期序列号（1900 日期系统）：46395 → 2027-01-08。"""
    match = _SERIAL.match(text or "")
    if not match:
        return None
    return date(1899, 12, 30) + timedelta(days=int(match.group(1)))


def _normalize_text(text: str) -> str:
    """全角数字 / 冒号 / 斜杠 → 半角；12 小时制"下午2:30" → 14:30（只换时间，不动日期）。"""
    import unicodedata

    text = unicodedata.normalize("NFKC", text or "")

    def to24(match):
        word, hour, minute = match.group(1), int(match.group(2)), int(match.group(3) or 0)
        if word.lower() in ("下午", "晚上", "pm") and hour < 12:
            hour += 12
        if word == "中午" and hour < 6:
            hour += 12
        if word.lower() in ("上午", "早上", "am") and hour == 12:
            hour = 0
        return f" {hour:02d}:{minute:02d}"

    text = _AMPM.sub(to24, text)
    # "14:30-4:30"：后半段小于前半段且不到 12 点，按同一个下午算
    def pm_end(match):
        h1, m1, h2, m2 = int(match.group(1)), match.group(2), int(match.group(3)), match.group(4)
        if h1 >= 12 and h2 < 12 and h2 + 12 > h1:
            h2 += 12
        return f"{h1:02d}:{m1}-{h2:02d}:{m2}"

    return re.sub(r"(?<!\d)(\d{1,2}):(\d{2})\s*[-~～—–至到]+\s*(\d{1,2}):(\d{2})", pm_end, text)


def parse_when(text: str, user: User, today: Optional[date] = None) -> Tuple[Optional[date], Optional[str], Optional[str], str, Optional[str]]:
    """
    从一段文字里找日期和时间。返回 (日期, 开始, 结束, 去掉日期时间后剩下的文字, 问题)。
    问题不为空时日期为 None（如写的是第几周但没设开学日期），预览里提示手动选日期。
    """
    today = today or timeutil.today()
    text = _normalize_text(text)
    rest, problem, day = text, None, None
    first = text.strip().split(" ")[0] if text.strip() else ""
    serial = _serial_date(first)
    if serial:
        day, rest = serial, text.strip()[len(first):]
    match = None if serial else (_FULL_DATE.search(rest) or _US_DATE.search(rest))
    if match:
        y, m, d = (match.group(1), match.group(2), match.group(3))
        if match.re is _US_DATE:
            m, d, y = y, m, d
        try:
            day = date(int(y), int(m), int(d))
        except ValueError:
            day = None
    if day is None and not match:
        match = _WEEK_DAY.search(rest)
        if match:
            day = _week_date(user, int(match.group(1)), WEEKDAYS[match.group(2)])
            if day is None:
                problem = f"写的是第 {match.group(1)} 周，没设开学日期，请手动选日期"
    if day is None and not match:
        match = _MD_CN.search(rest) or _MD_SLASH.search(rest)
        if match:
            day = _year_for(int(match.group(1)), int(match.group(2)), today)
    if match:
        rest = rest[:match.start()] + "  " + rest[match.end():]

    start = end = None
    # 日期数字（如 2027.1.8 里的 1.8）已经去掉，剩下的才找时间
    time_match = _TIME.search(rest)
    if time_match:
        start = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
        if time_match.group(3):
            end = f"{int(time_match.group(3)):02d}:{time_match.group(4)}"
        rest = rest[:time_match.start()] + "  " + rest[time_match.end():]
    else:
        period = _PERIODS.search(rest)
        if period:
            first = int(period.group(1))
            last = int(period.group(2) or first)
            times = schedule.period_times(user)
            if 1 <= first <= last <= len(times):
                start, end = times[first - 1]["start"], times[last - 1]["end"]
                rest = rest[:period.start()] + "  " + rest[period.end():]
    if end and start and end <= start:
        end = None
    rest = _WEEKDAY_WORD.sub("  ", rest)
    return day, start, end, rest, problem


# ---------------------------------------------------------------- 组装一条
def _match_subject(title: str, names: List[str]) -> str:
    for name in names:
        if name == title or (len(name) >= 2 and name in title) or (len(title) >= 2 and title in name):
            return name
    return ""


# 班级名里常见的简称 → 全称（只用于判断"是不是同一个班"，显示时保留表里最常用的写法）
CLASS_ABBR = (("软工", "软件工程"), ("计科", "计算机科学与技术"), ("网工", "网络工程"), ("信管", "信息管理"),
              ("电信", "电子信息"), ("自动化", "自动化"), ("工软", "工业软件"))
_CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _cn_to_int(text: str) -> str:
    """"十二" → "12"、"三" → "3"；只处理两位以内。"""
    if text == "十":
        return "10"
    if "十" in text:
        tens, _, ones = text.partition("十")
        return str((_CN_NUM.get(tens, 1) if tens else 1) * 10 + (_CN_NUM.get(ones, 0) if ones else 0))
    return "".join(str(_CN_NUM[c]) for c in text)


def class_key(name: str) -> str:
    """同一个班不同写法归成同一个键：全角 → 半角、去空白和括号、中文数字 → 阿拉伯数字、去掉"班 / 级 / 专业"、展开常见简称、
    年级"2025级 / 25级 / 25"统一成两位。"""
    import unicodedata

    text = unicodedata.normalize("NFKC", name or "").lower()
    text = re.sub(r"[\s()（）\[\]【】·._-]+", "", text)
    text = re.sub(r"[零一二两三四五六七八九十]+(?=班|$)", lambda m: _cn_to_int(m.group(0)), text)
    text = re.sub(r"^20(\d{2})", r"\1", text)
    text = text.replace("级", "").replace("专业", "")
    for short, full in CLASS_ABBR:
        if short != full and full not in text:
            text = text.replace(short, full)
    text = re.sub(r"班$", "", text)
    text = re.sub(r"(\D)0+(\d)", r"\1\2", text)
    return text


def merge_classes(items: List[dict], aliases: Optional[Dict[str, str]] = None) -> None:
    """把每场考试的班级名统一成同一个写法（就地修改）：先按模型给的别名表，再按 class_key 归并；
    同一组里取出现次数最多的写法（一样多时取较长、较完整的）。"""
    aliases = {str(k).strip(): str(v).strip() for k, v in (aliases or {}).items() if str(k).strip() and str(v).strip()}
    counts: Dict[str, int] = {}
    for item in items:
        item["classes"] = [aliases.get(c, c) for c in item.get("classes") or []]
        for name in item["classes"]:
            counts[name] = counts.get(name, 0) + 1
    groups: Dict[str, List[str]] = {}
    for name in counts:
        groups.setdefault(class_key(name), []).append(name)
    best = {}
    for names in groups.values():
        winner = max(names, key=lambda n: (counts[n], len(n)))
        for name in names:
            best[name] = winner
    for item in items:
        merged: List[str] = []
        for name in item["classes"]:
            if best.get(name, name) not in merged:
                merged.append(best.get(name, name))
        item["classes"] = merged


def split_classes(text: str) -> List[str]:
    """"25软件1班;25软件2班、25工业软件班" → 各个班级名（去重、保持顺序）。"""
    out: List[str] = []
    for part in re.split(r"[;；,，、/\s]+", text or ""):
        part = part.strip(" ()（）")
        if 2 <= len(part) <= 40 and part not in out:
            out.append(part)
    return out[:60]


def make_item(title: str, day: Optional[date], start: Optional[str], end: Optional[str], location: str = "",
              note: str = "", names: Optional[List[str]] = None, problem: Optional[str] = None,
              classes: str = "") -> dict:
    title = re.sub(r"\s+", " ", _LABEL.sub("", title or "")).strip(" -—:：")[:100]
    return {
        "title": title,
        "subject": _match_subject(title, names or [])[:80],
        "exam_date": day.isoformat() if day else "",
        "start_time": start or "",
        "end_time": end or "",
        "location": (location or "").strip()[:100],
        "note": (note or "").strip()[:500],
        "classes": split_classes(classes),
        "problem": problem or ("没有识别出日期，请手动选" if day is None else None),
    }


def parse_line(line: str, user: User, names: List[str], today: Optional[date] = None) -> Optional[dict]:
    """一行文字（或表格里没有表头的一行）：有日期 / 时间才算一场考试。"""
    line = (line or "").strip()
    if len(line) < 4:
        return None
    day, start, end, rest, problem = parse_when(line, user, today)
    if day is None and problem is None and start is None:
        return None
    notes = []
    seat = _SEAT.search(rest)
    if seat:
        notes.append(f"座位号 {seat.group(1)}")
        rest = rest[:seat.start()] + "  " + rest[seat.end():]
    location = ""
    place = _PLACE.search(rest)
    if place:
        location = place.group(1)
        rest = rest[:place.start()] + "  " + rest[place.end():]
    parts = [p.strip(" -—:：()（）") for p in _SPLIT.split(_LABEL_ANY.sub("  ", rest))]
    parts = [p for p in parts if p]
    if len(parts) == 1 and " " in parts[0]:
        parts = [p for p in parts[0].split(" ") if p]
    if not parts:
        return None
    title, others = parts[0], parts[1:]
    if not location:
        for index, value in enumerate(others):
            if _PLACE_LIKE.search(value) and len(value) <= 40:
                location = others.pop(index)
                break
    notes.extend(o for o in others if len(o) <= 40)
    return make_item(title, day, start, end, location, "；".join(notes), names, problem)
# ---------------------------------------------------------------- 表格 / 网页
def _header_map(row: List[str]) -> Dict[str, int]:
    found: Dict[str, int] = {}
    for index, raw in enumerate(row):
        cell = re.sub(r"\s+", "", raw or "")
        if not cell or len(cell) > 12 or any(word in cell for word in IGNORE):
            continue
        for field_name, words in HEADERS:
            if field_name not in found and any(word in cell for word in words):
                found[field_name] = index
                break
    return found


def _cell(row: List[str], index: Optional[int]) -> str:
    if index is None or index >= len(row):
        return ""
    # Excel 的日期单元格读出来可能带零点 "2026-01-08 00:00:00"，去掉免得被当成开考时间
    return re.sub(r"\s+00:00(?::00)?$", "", str(row[index] or "").strip())


def _hm_only(value: str) -> Optional[str]:
    """单独的开始 / 结束时间单元格："09:00"、"9:00:00"、"0.375"（Excel 时间小数）、"下午2:30"。"""
    value = _normalize_text(value or "").strip()
    if not value:
        return None
    if re.fullmatch(r"0?\.\d+", value):
        minutes = round(float(value) * 24 * 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}" if 0 <= minutes < 24 * 60 else None
    match = _TIME.search(value)
    return f"{int(match.group(1)):02d}:{match.group(2)}" if match else None


def parse_rows(rows: List[List[str]], user: User, names: List[str], today: Optional[date] = None) -> Tuple[List[dict], List[dict]]:
    """有表头（课程 + 日期/时间）时按列读；没有表头时每行拼成一句按文字解析。"""
    rows = [[str(c or "").strip() for c in row] for row in rows if any(str(c or "").strip() for c in row)]
    items, skipped = [], []
    header_index, columns = None, {}
    for index, row in enumerate(rows[:12]):
        found = _header_map(row)
        if "title" in found and ({"date", "time", "start", "week"} & found.keys()):
            header_index, columns = index, found
            break
    if header_index is None:
        for row in rows:
            item = parse_line("  ".join(row), user, names, today)
            if item:
                items.append(item)
        return items, skipped
    for row in rows[header_index + 1:]:
        title = _cell(row, columns.get("title"))
        week, weekday = _cell(row, columns.get("week")), _cell(row, columns.get("weekday"))
        # 周次、星期分两列（"18" / "星期五"）：拼成"第18周星期五"交给 parse_when
        week_part = ""
        if week and weekday:
            number = re.search(r"\d{1,2}", week)
            day_char = re.search(r"[一二三四五六日天1-7]", weekday.replace("星期", "").replace("周", ""))
            if number and day_char:
                week_part = f"第{number.group(0)}周星期{day_char.group(0)}"
        when = " ".join(v for v in (_cell(row, columns.get("date")), week_part, _cell(row, columns.get("time"))) if v)
        if title and _HEADER_WORDS.fullmatch(re.sub(r"\s+", "", title)):
            continue  # 表里重复出现的表头行（分页导出时常见）
        if not title and not when:
            continue
        if not title:
            skipped.append({"name": when[:60], "reason": "没有课程名称"})
            continue
        day, start, end, _, problem = parse_when(when, user, today)
        # 开始 / 结束时间单独成列时以它们为准
        start = _hm_only(_cell(row, columns.get("start"))) or start
        end = _hm_only(_cell(row, columns.get("end"))) or end
        if start and end and end <= start:
            end = None
        if day is None and problem is None and start is None:
            skipped.append({"name": title[:60], "reason": "没有考试日期或时间"})
            continue
        notes = []
        seat = _cell(row, columns.get("seat"))
        if seat:
            notes.append(f"座位号 {seat}")
        extra = _cell(row, columns.get("note"))
        if extra:
            notes.append(extra)
        items.append(make_item(title, day, start, end, _cell(row, columns.get("location")), "；".join(notes), names, problem,
                               _cell(row, columns.get("classes"))))
    return items, skipped


def _fill_down(rows: List[List[str]]) -> List[List[str]]:
    """PDF 表格里的合并单元格只有第一行有字：日期 / 时间这类列向下补齐（同一天的几场考试共用一个日期格）。"""
    out = [list(row) for row in rows]
    header_index, columns = None, {}
    for index, row in enumerate(out[:12]):
        found = _header_map(row)
        if "title" in found:
            header_index, columns = index, found
            break
    if header_index is None:
        return out
    for key in ("date", "time", "week", "weekday", "start", "end", "location"):
        col = columns.get(key)
        if col is None:
            continue
        last = ""
        for row in out[header_index + 1:]:
            if col >= len(row):
                continue
            if row[col]:
                last = row[col]
            elif last and any(row):
                row[col] = last
    return out


_HEADER_WORDS = re.compile(r"(?:课程名称|考试科目|考试名称|科目|课程)")


def _read_table(filename: str, content: bytes) -> List[List[str]]:
    """读表格：日期 / 时间单元格按类型换成文字，合并单元格的值填满整个区域（同一天的几场考试共用一个日期格）。"""
    from app.services.sheet_reader import filled, read_sheet

    try:
        return filled(read_sheet(filename, content))
    except ApiError as error:
        raise ApiError(error.status_code, error.message.replace("课表文件", "考试安排表格").replace("原始课表", "考试安排表格"),
                       error.data) from None


def _html_rows(filename: str, content: bytes) -> List[List[str]]:
    """网页里的表格（保存的 .html / .mhtml）：每个 <tr> 一行。只做静态解析，不执行脚本。"""
    from app.services import import_web

    documents = (import_web._mhtml_documents(content) if import_web._is_mhtml(filename, content)
                 else [import_web._decode(content)])
    rows: List[List[str]] = []
    for text in documents:
        parsed = import_web._parse_html(text)
        if parsed is None:
            continue
        for tr in parsed[0].iter("tr"):
            cells = [re.sub(r"\s+", " ", cell.text_content()).strip() for cell in tr if cell.tag in ("td", "th")]
            if any(cells):
                rows.append(cells)
            if len(rows) > 2000:
                return rows
    return rows


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ApiError(422, "文字编码无法识别，请另存为 UTF-8")


def parse_text(text: str, user: User, names: List[str], today: Optional[date] = None) -> Tuple[List[dict], List[dict]]:
    """复制的文字：从表格里复制的带制表符，按行列读（能用上表头）；其余逐行解析。"""
    text = (text or "")[:MAX_TEXT]
    lines = [line for line in text.splitlines() if line.strip()]
    if sum("\t" in line for line in lines) >= max(2, len(lines) // 2):
        return parse_rows([line.split("\t") for line in lines], user, names, today)
    return parse_rows([[line] for line in lines], user, names, today)
# ---------------------------------------------------------------- 大模型识别
SYSTEM_PROMPT = """你是考试安排识别助手。用户会给你考试安排的截图 / 照片，或从网页、PDF 复制出来的文字。
请找出每一场考试，只输出一个 JSON 对象，不要输出任何解释：
{"aliases": {"25软工1班": "25软件工程1班"},
 "exams": [{"title": "高等数学A", "date": "YYYY-MM-DD", "week": 18, "weekday": 3,
  "start_time": "09:00", "end_time": "11:00", "location": "教一 201", "seat": "15", "note": "闭卷",
  "classes": ["25软件工程1班", "25软件工程2班"]}]}
规则：
1. title 写课程名（或考试名），不要加"期末考试"等后缀，原文里有就照抄。
2. 日期只照抄原文里写的，不要推算、不要猜：
   · 写了年月日的，date 按原文换成 YYYY-MM-DD；中国的表格是"年/月/日"或"月/日"顺序，不是美式的"日/月"。
   · 只写了月日没写年份时，year 按今天往后最近的一次补上（考试安排一般是接下来的）。
   · 只写了"第几周 星期几"时，date 留空，填 week 与 weekday（星期一=1 … 星期日=7），由系统按开学日期换算。
   · 原文的日期和星期对不上时以日期为准，不要按星期改日期。
   · 表格里同一天几场考试共用一个合并的日期格时，下面几行沿用上一行的日期。
3. 时间用 24 小时制 HH:MM（"下午2:30"写 14:30）；写的是"第几节"时按用户给的节次时间换算；没写时间就留空字符串。
4. 地点、座位号、考试方式（开卷 / 闭卷 / 机考等）看不清就留空字符串，不要猜。
   原文列出了参加这场考试的班级时，把每个班级名写进 classes；没有就给空数组。
   同一个班在不同地方写法不同（如"25软工1班""2025级软件工程1班""软件工程(1)班"）时，全部统一成一个写法（用原文里最完整的那个），
   并在顶层 "aliases" 里列出其他写法 → 统一写法，如 {"25软工1班": "2025级软件工程1班"}；不同的班不要合并。
5. 表头、说明文字、已取消的考试都不要输出；不要编造原文里没有的考试。"""


def _context(user: User, today: date) -> str:
    periods = schedule.period_times(user)
    start = timeutil.parse_date(user.semester_start)
    term = f"本学期开学日期 {start.isoformat()}（第 1 周星期一）。" if start else ""
    return (f"今天是 {today.isoformat()}（{timeutil.weekday_label(today)}）。{term}本校节次时间："
            + "，".join(f"第{i}节 {p['start']}-{p['end']}" for i, p in enumerate(periods, start=1)) + "。")


def _model_items(user: User, config, text: Optional[str], parts: List[dict], names: List[str],
                 today: date, source: str) -> List[dict]:
    from app.ai import llm, vision

    intro = _context(user, today)
    if parts:
        content = [{"type": "text", "text": intro + ("\n同一文件提取的文字（仅供核对字形）：\n" + text[:4000] if text else "\n请识别这份考试安排。")},
                   *parts]
    else:
        content = f"{intro}\n以下是考试安排的文字：\n\n{(text or '')[:MODEL_TEXT]}"
    reply = vision._call(config, [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}],
                         with_images=bool(parts), source=source, what="考试安排")
    try:
        data = llm.extract_json(reply)
    except llm.LlmError:
        raise ApiError(502, "模型没有返回可识别的考试安排，请换一张更清晰的图片或重试", {"reason": "bad_output"}) from None
    raw = data.get("exams") if isinstance(data, dict) else None
    aliases = data.get("aliases") if isinstance(data, dict) and isinstance(data.get("aliases"), dict) else {}
    items = []
    for entry in (raw if isinstance(raw, list) else [])[:MAX_ITEMS]:
        if not isinstance(entry, dict) or not str(entry.get("title") or "").strip():
            continue
        day = timeutil.parse_date(str(entry.get("date") or "")) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(entry.get("date") or "")) else None
        problem = None
        if day is None:
            week, weekday = entry.get("week"), entry.get("weekday")
            if isinstance(week, int) and isinstance(weekday, int) and 1 <= weekday <= 7:
                day = _week_date(user, week, weekday)
                if day is None:
                    problem = f"写的是第 {week} 周，没设开学日期，请手动选日期"
        start, end = vision._hm(entry.get("start_time")), vision._hm(entry.get("end_time"))
        if start and end and end <= start:
            end = None
        notes = []
        if str(entry.get("seat") or "").strip():
            notes.append(f"座位号 {str(entry['seat']).strip()[:10]}")
        if str(entry.get("note") or "").strip():
            notes.append(str(entry["note"]).strip()[:60])
        raw_classes = entry.get("classes")
        classes = "；".join(str(c) for c in raw_classes) if isinstance(raw_classes, list) else str(raw_classes or "")
        items.append(make_item(str(entry["title"]), day, start, end, str(entry.get("location") or ""),
                               "；".join(notes), names, problem, classes))
    merge_classes(items, aliases)
    if text:
        _check_dates(items, text, user, today)
    return items


def _check_dates(items: List[dict], text: str, user: User, today: date) -> None:
    """模型给的日期和原文对一遍：原文里这门课那一行能本地读出日期、且和模型的不一样时，以原文为准，并标出来让同学核对。"""
    lines = [line for line in (text or "").splitlines() if line.strip()]
    for item in items:
        title = item["title"]
        if len(title) < 2:
            continue
        hits = [line for line in lines if title in line]
        if len(hits) != 1:
            continue  # 同一门课出现在多行（分场次）时分不清是哪一行，不改
        local, start, end, _, _ = parse_when(hits[0], user, today)
        if local is None or local.isoformat() == item["exam_date"]:
            continue
        item["exam_date"] = local.isoformat()
        item["start_time"] = item["start_time"] or (start or "")
        item["end_time"] = item["end_time"] or (end or "")
        item["problem"] = "日期按原文校正过，请核对"


def _looks_like_image(filename: str, content: bytes) -> bool:
    return (Path(filename or "").suffix.lower() in IMAGE_SUFFIXES or content[:8] == b"\x89PNG\r\n\x1a\n"
            or content[:3] == b"\xff\xd8\xff" or content[:4] == b"RIFF" or content[:2] == b"BM")
def _resolve_model(config_factory: Callable, vision_fallback, needs_vision: bool, source: str):
    """与课表识别相同：所选模型不能看图时换成服务器的视觉模型；没有可用模型时报 no_model。"""
    from app.ai import vision

    try:
        config = config_factory()
    except ApiError as error:
        if vision_fallback is not None and (error.data or {}).get("reason") == "no_model":
            return vision_fallback
        raise
    if needs_vision and not vision.supports_vision_guess(config):
        if vision_fallback is not None:
            return vision_fallback
        raise vision.no_vision_error(config, source)
    return config


def _page_text(content: bytes) -> str:
    from app.services import import_web

    text = import_web._decode(content)
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"[ \t\r\f\v]+", " ", text)


def preview(db: Session, user: User, *, filename: str = "", content: Optional[bytes] = None, text: Optional[str] = None,
            config_factory: Optional[Callable] = None, vision_fallback=None, today: Optional[date] = None) -> dict:
    """先在本地解析；解析不出（或是图片 / 扫描件）时交给大模型。返回预览，不写库。"""
    from app.ai import vision

    today = today or timeutil.today()
    names = sorted({c.course_name for c in schedule.user_courses(db, user) if c.course_name}, key=len, reverse=True)
    items, skipped, parts, raw_text, source = [], [], [], None, "image"
    suffix = Path(filename or "").suffix.lower()
    if text is not None:
        raw_text = text[:MAX_TEXT]
        items, skipped = parse_text(raw_text, user, names, today)
    elif content[:5] == b"%PDF-":
        from app.services.importer import _pdf_table_rows

        pdf_text, _ = vision._pdf_text(content)
        if len(re.sub(r"\s+", "", pdf_text)) >= 20:
            raw_text = pdf_text
            # 有表格线时按单元格还原行列（比按空格切更准）；没有表格线再按版式文字切列
            table = _pdf_table_rows(content)
            if table:
                items, skipped = parse_rows(_fill_down(table), user, names, today)
            if not items:
                rows = [re.split(r"\s{3,}", line.strip()) for line in pdf_text.splitlines() if line.strip()]
                items, skipped = parse_rows(rows, user, names, today)
        else:
            parts, source = vision._pdf_images(content), "pdf-image"
    elif _looks_like_image(filename, content):
        parts = [vision._image_part(vision._open_image(content))]
    elif suffix in TABLE_SUFFIXES:
        rows = _read_table(filename, content)
        raw_text = "\n".join("\t".join(r) for r in rows[:300])
        items, skipped = parse_rows(rows, user, names, today)
    elif suffix in HTML_SUFFIXES or suffix == ".mhtml" or content.lstrip()[:1] == b"<":
        rows = _html_rows(filename, content)
        raw_text = "\n".join("\t".join(r) for r in rows[:300]) or _page_text(content)
        items, skipped = parse_rows(rows, user, names, today)
    elif suffix in TEXT_SUFFIXES or not suffix:
        raw_text = _decode_text(content)[:MAX_TEXT]
        items, skipped = parse_text(raw_text, user, names, today)
    else:
        raise ApiError(415, f"支持{SUPPORTED}")

    model = None
    if not items:
        if not parts and not (raw_text or "").strip():
            raise ApiError(422, "内容是空的：请粘贴考试安排，或上传含考试安排的文件")
        if config_factory is None:
            raise ApiError(422, "没有找到考试安排：请确认内容里有课程名和考试日期", {"reason": "no_exams"})
        config = _resolve_model(config_factory, vision_fallback, bool(parts), source)
        items = _model_items(user, config, None if parts else raw_text, parts, names, today, source)
        model = vision.model_text(config)
    return build_preview(db, user, items, skipped, "ai" if model else "local", model, today)


def _existing_keys(db: Session, user: User) -> set:
    return {((e.title or "").strip(), e.exam_date) for e in db.query(Exam).filter(Exam.user_id == user.id)}


def build_preview(db: Session, user: User, items: List[dict], skipped: List[dict], source: str,
                  model: Optional[str], today: Optional[date] = None) -> dict:
    """去重、标出已有的和已过去的；只默认勾选"有日期、没过、还没添加过"的。"""
    today_text = (today or timeutil.today()).isoformat()
    existing = _existing_keys(db, user)
    merge_classes(items)
    seen, out = set(), []
    for item in items:
        # 同一门课按班级分场次时（同日不同时间 / 不同班级），每场都留着，让同学按班级挑
        key = (item["title"], item["exam_date"], item["start_time"], tuple(item.get("classes") or ()))
        if not item["title"] or key in seen:
            continue
        seen.add(key)
        item["duplicate"] = bool(item["exam_date"]) and (item["title"], item["exam_date"]) in existing
        past = bool(item["exam_date"]) and item["exam_date"] < today_text
        if past and not item["problem"]:
            item["problem"] = "日期已经过了"
        item["selected"] = bool(item["exam_date"]) and not item["duplicate"] and not past
        out.append(item)
        if len(out) >= MAX_ITEMS:
            break
    if not out:
        raise ApiError(422, "没有找到考试安排：请确认内容里有课程名和考试日期", {"reason": "no_exams", "skipped": skipped[:50]})
    out.sort(key=lambda i: (i["exam_date"] or "9999-99-99", i["start_time"]))
    # 表里出现过的班级（按出现场次多到少），前端据此让同学选"我的班级"
    counts: Dict[str, int] = {}
    for item in out:
        for name in item.get("classes") or ():
            counts[name] = counts.get(name, 0) + 1
    classes = sorted(counts, key=lambda name: (-counts[name], name))
    return {"items": out, "classes": classes, "skipped": skipped[:50], "source": source, "model": model, "count": len(out),
            "selected_count": sum(i["selected"] for i in out), "duplicate_count": sum(i["duplicate"] for i in out)}


def commit(db: Session, user: User, items: List[dict]) -> dict:
    """写入勾选的考试（已校验过的字段）；同名同日的已有考试跳过，不重复添加。"""
    from app.services.exams import exam_to_dict

    existing = _existing_keys(db, user)
    created, skipped = [], 0
    for item in items:
        key = (item["title"].strip(), item["exam_date"])
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        exam = Exam(user_id=user.id, **item)
        db.add(exam)
        created.append(exam)
    db.commit()
    for exam in created:
        db.refresh(exam)
    return {"created": [exam_to_dict(e) for e in created], "created_count": len(created), "skipped_count": skipped}
