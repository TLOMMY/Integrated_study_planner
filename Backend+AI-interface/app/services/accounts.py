# -*- coding: utf-8 -*-
"""账号序列化与邮箱验证码。"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core import timeutil
from app.core.config import settings
from app.core.errors import ApiError
from app.models import EmailCode, User


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
        "is_admin": bool(user.is_admin) or (user.email or "").lower() in settings.ADMIN_EMAILS,
        "email_verified": bool(user.email_verified),
        "theme": user.theme or "default",
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


# ---------------------------------------------------------------- v4 · B：邮箱验证码
CODE_TTL = timedelta(minutes=10)
CODE_COOLDOWN = timedelta(seconds=60)
CODE_MAX_ATTEMPTS = 5
PURPOSE_LABELS = {"register": "注册账号", "reset": "找回密码", "bind": "验证邮箱"}


def _code_hash(email: str, purpose: str, code: str) -> str:
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, f"{purpose}:{email.lower()}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def issue_email_code(db: Session, email: str, purpose: str) -> EmailCode:
    """生成并发送 6 位验证码：同一邮箱 60 秒内只能发一次，每天有上限；旧的未用验证码作废。"""
    from app.services import mail

    email = email.lower()
    current = timeutil.now()
    latest = db.query(EmailCode).filter(EmailCode.email == email).order_by(EmailCode.id.desc()).first()
    if latest is not None and latest.created_at and current - latest.created_at < CODE_COOLDOWN:
        wait = int((CODE_COOLDOWN - (current - latest.created_at)).total_seconds()) or 1
        raise ApiError(429, f"验证码发送太频繁，请 {wait} 秒后再试", {"retry_after": wait})
    day_start = current.replace(hour=0, minute=0, second=0)
    sent_today = db.query(EmailCode.id).filter(EmailCode.email == email, EmailCode.created_at >= day_start).count()
    if sent_today >= settings.EMAIL_CODE_DAILY_LIMIT:
        raise ApiError(429, "今天发送的验证码太多了，请明天再试")

    db.query(EmailCode).filter(EmailCode.email == email, EmailCode.purpose == purpose, EmailCode.used.is_(False)) \
        .update({EmailCode.used: True}, synchronize_session=False)
    code = f"{secrets.randbelow(10 ** 6):06d}"
    row = EmailCode(email=email, purpose=purpose, code_hash=_code_hash(email, purpose, code),
                    expires_at=current + CODE_TTL, created_at=current)
    db.add(row)
    label = PURPOSE_LABELS.get(purpose, "验证")
    body = (
        f"你好！\n\n你正在{label}，验证码是：{code}\n\n"
        f"验证码 {int(CODE_TTL.total_seconds() // 60)} 分钟内有效，请勿告诉他人。如果不是你本人操作，请忽略这封邮件。\n\n"
        f"—— {settings.APP_NAME}"
    )
    try:
        mail.send_mail(email, f"【学业管家】{label}验证码 {code}", body)
    except mail.MailError as exc:
        db.rollback()
        raise ApiError(502, str(exc))
    db.commit()
    return row


def verify_email_code(db: Session, email: str, purpose: str, code: str) -> None:
    """校验验证码：正确则标记已使用；错误累计次数，满 5 次作废。失败抛 ApiError(400)。"""
    email = email.lower()
    code = (code or "").strip()
    row = (
        db.query(EmailCode)
        .filter(EmailCode.email == email, EmailCode.purpose == purpose, EmailCode.used.is_(False))
        .order_by(EmailCode.id.desc())
        .first()
    )
    if row is None:
        raise ApiError(400, "请先获取验证码")
    if timeutil.now() > row.expires_at:
        row.used = True
        db.commit()
        raise ApiError(400, "验证码已过期，请重新获取")
    if not hmac.compare_digest(row.code_hash, _code_hash(email, purpose, code)):
        row.attempts = int(row.attempts or 0) + 1
        left = CODE_MAX_ATTEMPTS - row.attempts
        if left <= 0:
            row.used = True
        db.commit()
        raise ApiError(400, "验证码错误次数过多，请重新获取" if left <= 0 else f"验证码不正确，还可尝试 {left} 次")
    row.used = True
    db.commit()
