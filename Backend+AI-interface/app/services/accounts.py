# -*- coding: utf-8 -*-
"""账号序列化。"""

from app.core.config import settings
from app.models import User


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name or "",
        "display_name": user.full_name or user.username.split("@")[0],
        "avatar": user.avatar or "🦉",
        "daily_goal_minutes": int(user.daily_goal_minutes or 60),
        "semester": user.semester,
        "semester_start": user.semester_start,
        "total_weeks": int(user.total_weeks or 20),
        "is_demo": bool(user.is_demo),
        "phone": user.phone or "",
        "phone_masked": f"{user.phone[:3]}****{user.phone[-4:]}" if user.phone else "",
        "is_admin": (user.email or "").lower() in settings.ADMIN_EMAILS,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
