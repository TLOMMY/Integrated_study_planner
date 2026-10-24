# -*- coding: utf-8 -*-
"""
把"这周每天两小时复习高数和英语，晚上学"这类中文需求解析成结构化参数。
纯规则实现，无需联网；大模型可用时只负责润色排程，不负责理解参数。
"""

import re
from datetime import date, timedelta
from typing import Dict, List, Optional

CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_NUM = r"(\d+(?:\.\d+)?|[零一二两三四五六七八九十]+)"

# 常见课程简称 -> 用于在用户课表里找对应课程的关键词
SUBJECT_ALIASES: Dict[str, List[str]] = {
    "高数": ["数学分析", "高等数学", "微积分"],
    "数分": ["数学分析"],
    "高等数学": ["高等数学", "数学分析"],
    "微积分": ["微积分", "数学分析", "高等数学"],
    "线代": ["线性代数"],
    "线性代数": ["线性代数"],
    "概率": ["概率"],
    "概率论": ["概率"],
    "物理": ["物理"],
    "英语": ["英语"],
    "c++": ["C++", "程序设计"],
    "cpp": ["C++", "程序设计"],
    "编程": ["程序设计", "C++", "Python"],
    "python": ["Python"],
    "制图": ["制图", "工程设计"],
    "近代史": ["近现代史"],
    "思政": ["近现代史", "思想道德", "马克思"],
}
_GENERIC_SUBJECTS = {
    "高数": "高等数学", "数分": "数学分析", "线代": "线性代数", "概率": "概率论", "概率论": "概率论",
    "物理": "大学物理", "英语": "英语", "c++": "C++", "cpp": "C++", "python": "Python", "编程": "编程",
    "微积分": "微积分", "高等数学": "高等数学", "线性代数": "线性代数", "制图": "工程制图",
    "近代史": "中国近现代史", "思政": "思政",
}


def cn_number(token: str) -> Optional[float]:
    token = token.strip()
    if not token:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", token):
        return float(token)
    if token == "十":
        return 10
    if "十" in token:
        head, _, tail = token.partition("十")
        return (CN_DIGITS.get(head, 1) if head else 1) * 10 + (CN_DIGITS.get(tail, 0) if tail else 0)
    if len(token) == 1 and token in CN_DIGITS:
        return CN_DIGITS[token]
    return None


def _daily_minutes(text: str) -> Optional[int]:
    if m := re.search(_NUM + r"\s*个?半\s*(?:小时|钟头)", text):
        value = cn_number(m.group(1))
        if value is not None:
            return int((value + 0.5) * 60)
    if re.search(r"半\s*(?:个)?\s*(?:小时|钟头)", text):
        return 30
    if m := re.search(_NUM + r"\s*个?\s*(?:小时|钟头|h\b)", text, re.IGNORECASE):
        value = cn_number(m.group(1))
        if value is not None:
            return int(value * 60)
    if m := re.search(_NUM + r"\s*分钟", text):
        value = cn_number(m.group(1))
        if value is not None:
            return int(value)
    return None


# 显式日期：10.24 / 10/24 / 10月24日 / 24号
_MD_CN = r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?"
_MD_SEP = r"(\d{1,2})[./](\d{1,2})"
_RANGE_SEP = r"\s*(?:-|－|—|–|~|～|到|至)\s*"


def _make_date(ref: date, month: int, day: int) -> Optional[date]:
    """补全年份：比今天早 60 天以上的日期视为明年（如 12 月说 1.5）。"""
    for year in (ref.year, ref.year + 1):
        try:
            value = date(year, month, day)
        except ValueError:
            return None
        if value >= ref - timedelta(days=60):
            return value
    return None


def _pick(groups, i):
    """一个"月日"位置可能由中文写法或点号写法命中，取命中的那一组。"""
    return (groups[i], groups[i + 1]) if groups[i] else (groups[i + 2], groups[i + 3])


def _explicit_dates(text: str, ref: date) -> Optional[Dict[str, object]]:
    """识别"10.24-11.1""10月24日到11月1日""11月1日-10日""11月5号前""11月3日起 5 天"。"""
    full = rf"(?:{_MD_CN}|{_MD_SEP}){_RANGE_SEP}(?:{_MD_CN}|{_MD_SEP})"
    if m := re.search(full, text):
        g = m.groups()
        sm, sd = _pick(g, 0)
        em, ed = _pick(g, 4)
        start = _make_date(ref, int(sm), int(sd))
        end = _make_date(start, int(em), int(ed)) if start else None
        if start and end and end >= start:
            return {"start": start, "days": (end - start).days + 1, "explicit": True}
    # 省略结束月份：11月1日-10日 / 11.1-10号
    short = rf"(?:{_MD_CN}|{_MD_SEP}){_RANGE_SEP}(\d{{1,2}})\s*[日号]"
    if m := re.search(short, text):
        g = m.groups()
        sm, sd = _pick(g, 0)
        start = _make_date(ref, int(sm), int(sd))
        if start:
            end_day = int(g[4])
            month = start.month if end_day >= start.day else start.month % 12 + 1
            end = _make_date(start, month, end_day)
            if end and end >= start:
                return {"start": start, "days": (end - start).days + 1, "explicit": True}
    # 单个日期：只认"10月24日 / 10.24日 / 24号"，避免把"作业2.3""1.5小时"当成日期
    single_re = rf"{_MD_CN}|(\d{{1,2}})\.(\d{{1,2}})\s*[日号]|(?<![\d.月])(\d{{1,2}})\s*号"
    m = re.search(single_re, text)
    if not m:
        return None
    g = m.groups()
    if g[0]:
        single = _make_date(ref, int(g[0]), int(g[1]))
    elif g[2]:
        single = _make_date(ref, int(g[2]), int(g[3]))
    else:
        day = int(g[4])
        single = _make_date(ref, ref.month if day >= ref.day else ref.month % 12 + 1, day)
    if single is None:
        return None
    tail = text[m.end(): m.end() + 6]
    rest = text[: m.start()] + " " + text[m.end():]  # 去掉日期本身，免得"3日"被当成"3天"
    if re.match(r"\s*(?:之前|以前|前|截止|为止|考试|考|期中|期末)", tail):
        start = ref if single >= ref else single
        return {"start": start, "days": (single - start).days + 1, "explicit": True, "deadline": single}
    if re.match(r"\s*(?:起|开始|以后|之后)", tail):
        return {"start": single, "days": _duration_days(rest), "explicit": True}
    return {"start": single, "days": _duration_days(rest) or 1, "explicit": True}


def _duration_days(text: str) -> Optional[int]:
    # 排除"第13周"这种教学周写法，只认"两周/2个星期"这类时长
    if m := re.search(r"(?<![第\d零一二两三四五六七八九十])" + _NUM + r"\s*(?:个)?\s*(?:星期|周|礼拜)(?![一二三四五六日天])", text):
        value = cn_number(m.group(1))
        if value:
            return int(value * 7)
    if m := re.search(_NUM + r"\s*(?:天|日)(?!志)", text):
        value = cn_number(m.group(1))
        if value:
            return int(value)
    if re.search(r"一个月|一月", text):
        return 30
    return None


def _days(text: str, ref: date) -> Dict[str, object]:
    """
    返回 start / days / prefer / explicit。
    explicit=True 表示用户明确说了日期（具体日期或今天/明天/这周等），多轮对话时据此覆盖上一轮的范围；
    duration_only=True 表示只说了时长（如"改成5天"），起始日沿用上一轮。
    """
    return _explicit_dates(text, ref) or _relative_days(text, ref)


def _relative_days(text: str, ref: date) -> Dict[str, object]:
    """按"今晚 > 明天 > 这周 > N周 > N天"的顺序判断。"""
    if re.search(r"今晚|今天晚上", text):
        return {"start": ref, "days": 1, "prefer": "evening", "explicit": True}
    if re.search(r"今天|今日", text) and not re.search(r"今天起|今天开始", text):
        return {"start": ref, "days": 1, "explicit": True}
    if re.search(r"明晚", text):
        return {"start": ref + timedelta(days=1), "days": 1, "prefer": "evening", "explicit": True}
    if re.search(r"明天|明日", text) and not re.search(r"明天起|明天开始", text):
        return {"start": ref + timedelta(days=1), "days": 1, "explicit": True}
    if re.search(r"后天", text):
        return {"start": ref + timedelta(days=2), "days": 1, "explicit": True}
    if re.search(r"周末", text):
        saturday = ref + timedelta(days=(5 - ref.weekday()) % 7)
        return {"start": saturday, "days": 2, "explicit": True}
    start = ref + timedelta(days=1) if re.search(r"明天起|明天开始", text) else ref
    if re.search(r"(?<!下)(?:这周|本周|这个星期)", text):
        left = 7 - start.weekday()
        # 周五以后说"这周"只剩两三天，顺延到下周日，避免计划过短
        if left < 3:
            return {"start": start, "days": left + 7, "explicit": True, "extended": left}
        return {"start": start, "days": left, "explicit": True}
    if re.search(r"下周", text):
        monday = ref + timedelta(days=7 - ref.weekday())
        return {"start": monday, "days": 7, "explicit": True}
    duration = _duration_days(text)
    explicit_start = start != ref or bool(re.search(r"今天起|今天开始", text))
    return {"start": start, "days": duration, "explicit": explicit_start,
            "duration_only": duration is not None and not explicit_start}


def _subjects(text: str, course_names: List[str]) -> List[str]:
    lowered = text.lower()
    found: List[str] = []

    def add(name: str) -> None:
        if name and name not in found:
            found.append(name)

    for name in course_names:
        short = re.sub(r"[（(].*?[)）]", "", name).strip()
        if short and (short.lower() in lowered or name.lower() in lowered):
            add(name)
    for alias, keywords in SUBJECT_ALIASES.items():
        if alias not in lowered:
            continue
        matched = [name for name in course_names if any(k.lower() in name.lower() for k in keywords)]
        if matched:
            for name in matched[:1]:
                add(name)
        else:
            add(_GENERIC_SUBJECTS.get(alias, alias))
    if not found:
        m = re.search(r"(?:复习|准备|学习|预习|备考|攻克)\s*([一-龥A-Za-z+]{2,10})", text)
        if m:
            candidate = re.sub(r"(计划|一下|内容|的|吧|考试)$", "", m.group(1))
            if len(candidate) >= 2 and candidate not in {"计划", "安排", "一下", "时间"}:
                add(candidate)
    return found[:5]


def parse_request(text: str, ref: date, course_names: List[str]) -> dict:
    text = (text or "").strip()
    span = _days(text, ref)
    prefer = span.get("prefer")
    if re.search(r"早上|上午|清晨|早起", text):
        prefer = "morning"
    elif re.search(r"下午", text):
        prefer = "afternoon"
    elif re.search(r"晚上|晚间|夜里", text):
        prefer = prefer or "evening"

    intensity = 1.0
    if re.search(r"轻松|少一点|减少|别太累|放松|累了", text):
        intensity = 0.7
    elif re.search(r"加强|多一点|冲刺|拼一把|高强度", text):
        intensity = 1.3

    exam = bool(re.search(r"考试|期末|期中|备考|考前|测验|四级|六级|考研", text))
    return {
        "start": span["start"],
        "days": span["days"],
        "date_explicit": bool(span.get("explicit")),
        "duration_only": bool(span.get("duration_only")),
        "extended": span.get("extended"),
        "deadline": span.get("deadline"),
        "daily_minutes": _daily_minutes(text),
        "prefer": prefer,
        "intensity": intensity,
        "exam": exam,
        "subjects": _subjects(text, course_names),
    }
