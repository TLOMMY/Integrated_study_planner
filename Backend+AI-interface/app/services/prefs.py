# -*- coding: utf-8 -*-
"""
学习时段偏好。

- 自动（auto）：统计近 60 天的专注记录，按开始时刻落在上午 / 下午 / 晚上的分钟数排序，
  专注越多的时段在 AI 排程时越优先；记录不足 5 小时时不做偏好。
- 自定义（custom）：用户在设置里指定偏好时段、避开时段、最早 / 最晚时间、单次时长、休息时长。

AI 规划（规则引擎与大模型）都从 effective(db, user) 读取最终生效的偏好。
"""

import json
from collections import Counter
from datetime import timedelta
from typing import Dict

from sqlalchemy.orm import Session

from app.core import timeutil
from app.models import FocusRecord, User

SEGMENT_LABELS = {"morning": "上午", "afternoon": "下午", "evening": "晚上"}
DEFAULTS = {
    "mode": "auto",
    "segments": [],
    "avoid": [],
    "earliest": "08:00",
    "latest": "22:00",
    "block_minutes": 45,
    "rest_minutes": 10,
    "daily_minutes": None,
}
PROFILE_DAYS = 60
MIN_PROFILE_MINUTES = 300


def load(user: User) -> dict:
    try:
        stored = json.loads(user.study_prefs) if user.study_prefs else {}
    except (TypeError, ValueError):
        stored = {}
    return {**DEFAULTS, **{k: v for k, v in stored.items() if k in DEFAULTS}}


def save(user: User, data: dict) -> None:
    user.study_prefs = json.dumps({k: data.get(k, DEFAULTS[k]) for k in DEFAULTS}, ensure_ascii=False)


def _segment_of(hour: int) -> str:
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def focus_profile(db: Session, user: User) -> dict:
    """近 60 天专注时间的时段分布与 24 小时分布。"""
    since = (timeutil.today() - timedelta(days=PROFILE_DAYS - 1)).isoformat()
    rows = (
        db.query(FocusRecord.started_at, FocusRecord.ended_at, FocusRecord.duration_minutes)
        .filter(FocusRecord.user_id == user.id, FocusRecord.record_date >= since)
        .all()
    )
    by_segment: Counter = Counter()
    by_hour = [0] * 24
    sessions = 0
    for started_at, ended_at, minutes in rows:
        minutes = int(minutes or 0)
        moment = started_at or (ended_at - timedelta(minutes=minutes) if ended_at else None)
        if moment is None or minutes <= 0:
            continue
        sessions += 1
        by_hour[moment.hour] += minutes
        by_segment[_segment_of(moment.hour)] += minutes
    total = sum(by_segment.values())
    ranked = [seg for seg, _ in by_segment.most_common() if by_segment[seg] > 0]
    peak = max(range(24), key=lambda h: by_hour[h]) if total else None
    return {
        "days": PROFILE_DAYS,
        "sessions": sessions,
        "total_minutes": total,
        "segments": [
            {"key": key, "label": label, "minutes": by_segment.get(key, 0),
             "share": round(by_segment.get(key, 0) / total * 100) if total else 0}
            for key, label in SEGMENT_LABELS.items()
        ],
        "by_hour": by_hour,
        "peak_hour": peak,
        "ranked": ranked,
        "enough": total >= MIN_PROFILE_MINUTES,
    }


def effective(db: Session, user: User, profile: Dict = None) -> dict:
    """最终生效的排程偏好。"""
    prefs = load(user)
    profile = profile or focus_profile(db, user)
    if prefs["mode"] == "custom":
        segments = list(prefs["segments"])
        source = "custom"
    else:
        segments = profile["ranked"] if profile["enough"] else []
        source = "auto" if segments else "default"
    return {
        "source": source,
        "segments": segments,
        "avoid": list(prefs["avoid"]) if prefs["mode"] == "custom" else [],
        "earliest": prefs["earliest"] if prefs["mode"] == "custom" else DEFAULTS["earliest"],
        "latest": prefs["latest"] if prefs["mode"] == "custom" else DEFAULTS["latest"],
        "block_minutes": int(prefs["block_minutes"]) if prefs["mode"] == "custom" else None,
        "rest_minutes": int(prefs["rest_minutes"]) if prefs["mode"] == "custom" else DEFAULTS["rest_minutes"],
        "daily_minutes": prefs["daily_minutes"] if prefs["mode"] == "custom" else None,
    }


def describe(eff: dict) -> str:
    """给前端和大模型看的一句话说明。"""
    parts = []
    if eff["segments"]:
        parts.append("优先" + "、".join(SEGMENT_LABELS[s] for s in eff["segments"]))
    if eff["avoid"]:
        parts.append("避开" + "、".join(SEGMENT_LABELS[s] for s in eff["avoid"]))
    parts.append(f"{eff['earliest']}-{eff['latest']} 之间")
    if eff["block_minutes"]:
        parts.append(f"每段约 {eff['block_minutes']} 分钟")
    prefix = {"custom": "自定义", "auto": "按你的专注习惯", "default": "默认"}[eff["source"]]
    return f"{prefix}：" + "，".join(parts)


def to_dict(db: Session, user: User) -> dict:
    profile = focus_profile(db, user)
    eff = effective(db, user, profile)
    return {"prefs": load(user), "profile": profile, "effective": {**eff, "text": describe(eff)}}
