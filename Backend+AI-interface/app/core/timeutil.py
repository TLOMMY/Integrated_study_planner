# -*- coding: utf-8 -*-
"""
日期时间工具。

全系统统一使用"本地无时区时间"：数据库存 naive datetime，接口传 "YYYY-MM-DD" 与 "HH:MM"。
today()/now() 集中在这里，测试可以整体替换。
"""

from datetime import date, datetime, timedelta
from typing import Optional

WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


def today() -> date:
    return now().date()


def parse_date(value: Optional[str], default: Optional[date] = None) -> Optional[date]:
    if not value:
        return default
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return default


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def hm_to_minutes(value: str) -> int:
    hours, minutes = str(value).strip()[:5].split(":")
    return int(hours) * 60 + int(minutes)


def minutes_to_hm(value: int) -> str:
    value = max(0, min(int(value), 23 * 60 + 59))
    return f"{value // 60:02d}:{value % 60:02d}"


def combine(day: date, hm: str) -> datetime:
    return datetime.combine(day, datetime.strptime(hm[:5], "%H:%M").time())


def weekday_label(day: date) -> str:
    return f"周{WEEKDAY_CN[day.weekday()]}"
