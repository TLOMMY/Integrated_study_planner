# -*- coding: utf-8 -*-
"""用户模型。学期设置、每日目标等个人偏好也存放在这里。"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.core.database import Base
from app.core.timeutil import now


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    full_name = Column(String(100), nullable=True)
    avatar = Column(String(16), nullable=True, default="🦉")
    is_active = Column(Boolean, default=True)
    is_demo = Column(Boolean, default=False)

    # 每日专注目标（分钟），对应多邻国的"每日目标"
    daily_goal_minutes = Column(Integer, default=60)

    # 学期设置，对应 WakeUp 课程表的"开学日期 / 总周数 / 节次时间"
    semester = Column(String(40), nullable=True)
    semester_start = Column(String(10), nullable=True)
    total_weeks = Column(Integer, default=20)
    period_times = Column(Text, nullable=True)

    # AI 规划使用的模型：auto（服务器配置或规则引擎）/ rule / 某个 ai_providers.id
    ai_provider = Column(String(20), default="auto")

    # 账号安全：绑定手机号（仅保存，暂无短信验证）；改密码 / 退出全部设备时 +1，使旧登录凭证失效
    phone = Column(String(20), nullable=True)
    token_version = Column(Integer, default=0)

    # 学习时段偏好（JSON）：mode=auto 按专注记录自动学习，custom 使用用户设定；AI 排程会读取
    study_prefs = Column(Text, nullable=True)

    # v4：管理员（也可用 .env 的 ADMIN_EMAILS 指定）、邮箱是否已验证
    is_admin = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    # 断签保护卡数量
    streak_freezes = Column(Integer, default=0)
    # 进行中的专注（JSON），用于跨设备同步
    focus_state = Column(Text, nullable=True)
    # 界面主题（default / dark / 其他主题名），跨设备同步
    theme = Column(String(30), default="default")
    # v4 · A：使用服务器配置的模型（ai_provider=auto）时的思考强度 off / high / max
    ai_thinking = Column(String(10), default="high")
    # v4 · B：最近活跃时间（每 5 分钟最多写一次）与最近 60 天的活跃日期（逗号分隔，供后台统计日活/周活）
    last_seen_at = Column(DateTime, nullable=True)
    active_days = Column(Text, nullable=True)

    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)
