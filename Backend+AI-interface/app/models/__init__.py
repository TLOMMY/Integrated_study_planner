"""数据库模型。"""

from app.models.ai import AiProvider
from app.models.game import UserAchievement, XpEvent
from app.models.study import FocusRecord, ImportLog, StudyPlan, StudyTask, Timetable
from app.models.user import User
from app.models.v4 import (
    AppSetting, ChatConversation, ChatMessage, ClientError, EmailCode, Exam, Feedback, StreakFreeze, StudyGroup,
    StudyGroupMember, TimetableShare, WeeklyReport,
)

__all__ = [
    "User",
    "StudyPlan",
    "StudyTask",
    "Timetable",
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
]
