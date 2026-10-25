# -*- coding: utf-8 -*-
"""密码哈希、JWT 签发与当前用户依赖。"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core import timeutil
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.models import User

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    if not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        # 旧数据里可能存在明文或无法识别的哈希，一律视为校验失败
        return False


def create_access_token(user: User, expires_minutes: Optional[int] = None) -> str:
    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    payload = {
        "sub": str(user.id),
        "user_id": user.id,
        "username": user.username,
        # 改密码 / 退出全部设备后版本号 +1，旧凭证随即失效
        "ver": int(user.token_version or 0),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def token_payload(user: User) -> dict:
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise ApiError(401, "请先登录")

    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "登录已过期，请重新登录")
    except jwt.PyJWTError:
        raise ApiError(401, "登录凭证无效，请重新登录")

    user_id = payload.get("user_id")
    if user_id is None and str(payload.get("sub", "")).isdigit():
        user_id = int(payload["sub"])

    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise ApiError(401, "账号不存在，请重新登录")
    if int(payload.get("ver", 0)) != int(user.token_version or 0):
        raise ApiError(401, "密码已修改或已在其他设备退出，请重新登录")
    if not user.is_active:
        raise ApiError(403, "账号已被停用")
    touch_last_seen(db, user)
    return user


# ---------------------------------------------------------------- v4 · B：活跃记录、管理员、可选登录
SEEN_INTERVAL = timedelta(minutes=5)
ACTIVE_DAYS_KEEP = 60


def touch_last_seen(db: Session, user: User) -> None:
    """更新最近活跃时间：每 5 分钟最多写一次库；跨天时记下活跃日期（后台统计日活/周活用）。"""
    current = timeutil.now()
    if user.last_seen_at and current - user.last_seen_at < SEEN_INTERVAL:
        return
    user.last_seen_at = current
    day = current.date().isoformat()
    days = [d for d in (user.active_days or "").split(",") if d]
    if day not in days:
        cutoff = (current.date() - timedelta(days=ACTIVE_DAYS_KEEP)).isoformat()
        user.active_days = ",".join([d for d in days if d >= cutoff] + [day])
    try:
        db.commit()
    except Exception:  # noqa: BLE001 - 活跃记录写失败不影响正常请求
        db.rollback()


def is_admin_user(user: Optional[User]) -> bool:
    return bool(user) and (bool(user.is_admin) or (user.email or "").lower() in settings.ADMIN_EMAILS)


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not is_admin_user(user):
        raise ApiError(403, "只有管理员可以访问")
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """登录可选的接口使用：凭证缺失或无效时返回 None，不报错。"""
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user = db.get(User, int(payload.get("user_id") or payload.get("sub")))
    except (jwt.PyJWTError, TypeError, ValueError):
        return None
    if user is None or not user.is_active or int(payload.get("ver", 0)) != int(user.token_version or 0):
        return None
    return user
