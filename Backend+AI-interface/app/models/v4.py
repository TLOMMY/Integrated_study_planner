# -*- coding: utf-8 -*-
"""
v4 新增的表：问题反馈、邮箱验证码、AI 对话、考试、课表分享、学习小组、断签保护、周报、前端错误、系统设置。

所有 JSON 字段用 Text 存（SQLite），读写时 json.loads / json.dumps。
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.core.database import Base
from app.core.timeutil import now


class Feedback(Base):
    """用户反馈。同时仍会写一份 txt 到 FEEDBACK_DIR，方便直接在服务器上查看。"""

    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    category = Column(String(20), default="bug")
    content = Column(Text, nullable=False)
    contact = Column(String(100), nullable=True)
    page = Column(String(200), nullable=True)
    client = Column(String(300), nullable=True)
    # 截图相对路径列表（JSON），文件存在 FEEDBACK_DIR/images/ 下
    images = Column(Text, nullable=True)
    # open / processing / resolved / closed
    status = Column(String(20), default="open", index=True)
    reply = Column(Text, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    replied_by = Column(Integer, nullable=True)
    # 用户是否已读最新回复
    user_unread = Column(Boolean, default=False)
    txt_name = Column(String(80), nullable=True)
    created_at = Column(DateTime, default=now, index=True)
    updated_at = Column(DateTime, default=now, onupdate=now)


class EmailCode(Base):
    """邮箱验证码（注册验证 / 找回密码 / 换绑邮箱）。只存哈希。"""

    __tablename__ = "email_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), nullable=False, index=True)
    # register / reset / bind
    purpose = Column(String(20), nullable=False)
    code_hash = Column(String(200), nullable=False)
    attempts = Column(Integer, default=0)
    used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=now)


class ChatConversation(Base):
    """AI 对话（存服务器，跨设备同步）。"""

    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(100), default="新对话")
    # 结构化记忆（科目、日期范围、偏好、要点），JSON
    memory = Column(Text, nullable=True)
    archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now, index=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # user / assistant
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=True)
    # 助手回合的附加数据（JSON）：思考摘要、调用过的工具、提案（创建/修改任务与课程）、导入结果
    meta = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now, index=True)


class Exam(Base):
    """考试倒计时。"""

    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(100), nullable=False)
    subject = Column(String(80), nullable=True)
    exam_date = Column(String(10), nullable=False, index=True)
    start_time = Column(String(5), nullable=True)
    location = Column(String(100), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class TimetableShare(Base):
    """课表分享：生成分享码，同学输入分享码即可导入。"""

    __tablename__ = "timetable_shares"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(16), unique=True, nullable=False, index=True)
    semester = Column(String(40), nullable=True)
    # 课程快照与学期设置（JSON）
    payload = Column(Text, nullable=False)
    import_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now)


class StudyGroup(Base):
    """学习小组 / 班级：组内排行榜。"""

    __tablename__ = "study_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(40), nullable=False)
    invite_code = Column(String(16), unique=True, nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=now)


class StudyGroupMember(Base):
    __tablename__ = "study_group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_member"),)

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("study_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at = Column(DateTime, default=now)


class StreakFreeze(Base):
    """
    断签保护卡流水。kind：
    - used：这一天被保护卡补上，连续天数计算时视为已学习；
    - earned：这一天连续学习满 7 的倍数天，获得 1 张；
    - capped：满 7 天时已持有 3 张（上限），只记录"已处理"，不发卡。
    同一天只会有一条（学习日只可能 earned/capped，缺勤日只可能 used）。
    """

    __tablename__ = "streak_freezes"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_streak_freeze_day"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    day = Column(String(10), nullable=False)
    kind = Column(String(10), default="used", index=True)
    created_at = Column(DateTime, default=now)


class WeeklyReport(Base):
    """每周学习报告 / AI 复盘缓存。"""

    __tablename__ = "weekly_reports"
    __table_args__ = (UniqueConstraint("user_id", "week_start", "kind", name="uq_weekly_report"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start = Column(String(10), nullable=False)
    # stats（统计报告）/ ai（AI 复盘）
    kind = Column(String(20), default="stats")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=now)


class ClientError(Base):
    """前端上报的运行时错误，便于定位线上问题。"""

    __tablename__ = "client_errors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    message = Column(String(500), nullable=False)
    stack = Column(Text, nullable=True)
    page = Column(String(200), nullable=True)
    client = Column(String(300), nullable=True)
    app_version = Column(String(20), nullable=True)
    count = Column(Integer, default=1)
    fingerprint = Column(String(64), nullable=False, index=True)
    last_seen = Column(DateTime, default=now)
    created_at = Column(DateTime, default=now)


class AppSetting(Base):
    """管理员在后台修改的系统设置（如反馈通知机器人地址），优先于 .env。"""

    __tablename__ = "app_settings"

    key = Column(String(60), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=now, onupdate=now)
