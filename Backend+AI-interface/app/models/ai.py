# -*- coding: utf-8 -*-
"""用户自定义的大模型接入配置（OpenAI 兼容协议）。"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.core.database import Base
from app.core.timeutil import now


class AiProvider(Base):
    __tablename__ = "ai_providers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(40), nullable=False)
    base_url = Column(String(300), nullable=False)
    model = Column(String(120), nullable=False)
    # Fernet 密文，明文 Key 永不出库、永不返回前端
    api_key_enc = Column(Text, nullable=True)
    # 思考强度：off / high / max（只对支持思考模式的模型生效，其他模型自动不传）
    thinking = Column(String(10), default="high")
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)
