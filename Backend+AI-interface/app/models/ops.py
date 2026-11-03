# -*- coding: utf-8 -*-
"""
上线必需新增的表：AI 用量计数、限流 / 登录锁定事件。

都存在同一个 SQLite 里，服务重启后限额与锁定状态不会丢失。
"""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint

from app.core.database import Base
from app.core.timeutil import now


class AiUsage(Base):
    """每用户每天使用服务器 DeepSeek Key 的次数与 token（用户自己的 Key 不记）。"""

    __tablename__ = "ai_usage"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_ai_usage_user_day"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # YYYY-MM-DD（服务器本地日期，与 timeutil.today() 一致）
    day = Column(String(10), nullable=False, index=True)
    calls = Column(Integer, default=0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    updated_at = Column(DateTime, default=now, onupdate=now)


class RateEvent(Base):
    """
    滑动窗口计数的一次事件：登录失败（bucket=login-fail）、各接口限流、5xx / 前端错误告警计数。
    ts 为 Unix 时间戳（秒），过期记录会被定期清理。
    """

    __tablename__ = "rate_events"
    __table_args__ = (Index("ix_rate_events_bucket_key_ts", "bucket", "key", "ts"),)

    id = Column(Integer, primary_key=True)
    bucket = Column(String(40), nullable=False)
    key = Column(String(200), nullable=False)
    ts = Column(Float, nullable=False, index=True)
