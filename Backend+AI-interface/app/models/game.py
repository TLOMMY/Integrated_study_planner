# -*- coding: utf-8 -*-
"""成长体系：XP 流水与成就解锁记录。"""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.core.database import Base
from app.core.timeutil import now, today


class XpEvent(Base):
    """
    XP 流水。每条奖励都有 ref，(user_id, reason, ref) 唯一，
    保证"同一任务完成两次只加一次分""每日目标一天只奖励一次"。
    """

    __tablename__ = "xp_events"
    __table_args__ = (UniqueConstraint("user_id", "reason", "ref", name="uq_xp_event_ref"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    reason = Column(String(40), nullable=False)
    ref = Column(String(80), nullable=False)
    event_date = Column(Date, default=today, index=True)
    created_at = Column(DateTime, default=now)


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_user_achievement"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(40), nullable=False)
    unlocked_at = Column(DateTime, default=now)
