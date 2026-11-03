"""数据库模型。"""

from app.models.ai import AiProvider
from app.models.game import UserAchievement, XpEvent
from app.models.study import FocusRecord, ImportLog, StudyPlan, StudyTask, Timetable, TimetableSet
from app.models.user import User
from app.models.v4 import (
    AppSetting, ChatConversation, ChatMessage, ClientError, EmailCode, Exam, Feedback, StreakFreeze, StudyGroup,
    StudyGroupMember, TimetableShare, WeeklyReport,
)
# ---- AI 用量、限流事件
from app.models.ops import AiUsage, RateEvent

__all__ = [
    "User",
    "StudyPlan",
    "StudyTask",
    "Timetable",
    "TimetableSet",
    "FocusRecord",
    "ImportLog",
    "XpEvent",
    "UserAchievement",
    "AiProvider",
    "Feedback",
    "EmailCode",
    "ChatConversation",
    "ChatMessage",
    "Exam",
    "TimetableShare",
    "StudyGroup",
    "StudyGroupMember",
    "StreakFreeze",
    "WeeklyReport",
    "ClientError",
    "AppSetting",
    "AiUsage",
    "RateEvent",
]
