# -*- coding: utf-8 -*-
from typing import Optional

from fastapi import APIRouter, Depends, Request

from app.api.deps import DB, CurrentUser
from app.core import ratelimit
from app.core.config import settings
from app.core.errors import ApiError, ok
from app.core.security import get_optional_user, hash_password, token_payload, verify_password
from app.models import User
from app.schemas import EmailCodeIn, LoginIn, RegisterIn, ResetPasswordIn
from app.services import mail, schedule
from app.services.accounts import CODE_COOLDOWN, CODE_TTL, issue_email_code, user_to_dict, verify_email_code

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", summary="注册（成功后直接返回登录凭证）")
def register(payload: RegisterIn, db: DB):
    email = payload.email.lower()
    username = payload.username or email
    if db.query(User.id).filter(User.email == email).first():
        raise ApiError(400, "该邮箱已注册，请直接登录")
    if db.query(User.id).filter(User.username == username).first():
        raise ApiError(400, "用户名已被占用")
    verified = False
    if payload.code:
        verify_email_code(db, email, "register", payload.code)
        verified = True
    elif settings.REQUIRE_EMAIL_VERIFY:
        raise ApiError(400, "请填写邮箱验证码")
    user = User(
        username=username,
        email=email,
        full_name=payload.full_name or email.split("@")[0],
        avatar="🦉",
        hashed_password=hash_password(payload.password),
        semester=schedule.guess_semester(),
        email_verified=verified,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return ok({**token_payload(user), "user": user_to_dict(user)}, "注册成功")


@router.post("/login", summary="登录（邮箱或用户名）")
def login(payload: LoginIn, db: DB):
    account = payload.account
    key = account.strip().lower()
    locked = ratelimit.remaining_lock_seconds(key)
    if locked:
        raise ApiError(429, f"密码错误次数过多，请 {max(1, round(locked / 60))} 分钟后再试")
    user = db.query(User).filter((User.username == account) | (User.email == account.lower())).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        left = ratelimit.record_failure(key)
        raise ApiError(401, f"账号或密码错误，还可尝试 {left} 次" if left <= 2 else "账号或密码错误")
    ratelimit.reset(key)
    if not user.is_active:
        raise ApiError(403, "账号已被停用")
    return ok({**token_payload(user), "user": user_to_dict(user)}, "登录成功")


@router.post("/refresh", summary="续期登录凭证")
def refresh(user: CurrentUser):
    return ok(token_payload(user), "凭证已续期")


@router.post("/demo", summary="一键体验演示账号")
def demo_login(db: DB):
    if not settings.SEED_DEMO:
        raise ApiError(404, "演示账号未开启")
    from app.services.seed import DEMO_USERNAME, ensure_demo

    user = db.query(User).filter(User.username == DEMO_USERNAME).first() or ensure_demo(db)
    if not user.is_active:
        raise ApiError(403, "演示账号已被停用")
    return ok({**token_payload(user), "user": user_to_dict(user)}, "已进入演示账号")


# ---------------------------------------------------------------- v4 · B：邮箱验证码、找回密码
@router.get("/options", summary="登录页需要的开关：注册是否必须验证邮箱、能否发送邮件")
def auth_options():
    return ok({"require_email_verify": settings.REQUIRE_EMAIL_VERIFY, "mail_enabled": mail.can_deliver()})


@router.post("/email-code", summary="发送邮箱验证码（register 注册 / reset 找回密码 / bind 验证或换绑邮箱，bind 需登录）")
def send_email_code(payload: EmailCodeIn, request: Request, db: DB, user: Optional[User] = Depends(get_optional_user)):
    if not ratelimit.hit("email-code-ip", ratelimit.client_ip(request), 20, 3600):
        raise ApiError(429, "请求过于频繁，请稍后再试")
    email = payload.email.lower()
    owner = db.query(User).filter(User.email == email).first()
    deliver = True
    if payload.purpose == "register":
        if owner is not None:
            raise ApiError(400, "该邮箱已注册，请直接登录")
    elif payload.purpose == "bind":
        if user is None:
            raise ApiError(401, "请先登录")
        if user.is_demo:
            raise ApiError(403, "演示账号不支持验证邮箱，请注册自己的账号")
        if owner is not None and owner.id != user.id:
            raise ApiError(400, "该邮箱已被其他账号使用")
    else:
        # 找回密码：不透露邮箱是否注册，未注册或演示账号时不实际发送
        deliver = owner is not None and not owner.is_demo and owner.is_active
    if deliver:
        issue_email_code(db, email, payload.purpose)
    hint = "验证码已发送，请查收邮件（可能在垃圾箱里）" if mail.can_deliver() else "服务器未配置邮件发送，验证码已写入后端日志"
    if payload.purpose == "reset":
        hint = "如果该邮箱已注册，验证码已发送，请查收邮件" if mail.can_deliver() else hint
    return ok({"cooldown": int(CODE_COOLDOWN.total_seconds()), "expires_in": int(CODE_TTL.total_seconds()),
               "mail_enabled": mail.can_deliver()}, hint)


@router.post("/reset-password", summary="用邮箱验证码重设密码（所有设备上的旧登录随即失效）")
def reset_password(payload: ResetPasswordIn, request: Request, db: DB):
    if not ratelimit.hit("reset-password-ip", ratelimit.client_ip(request), 30, 3600):
        raise ApiError(429, "请求过于频繁，请稍后再试")
    email = payload.email.lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or user.is_demo:
        # 与验证码错误同样的提示，不透露邮箱是否注册
        raise ApiError(400, "请先获取验证码")
    verify_email_code(db, email, "reset", payload.code)
    if not user.is_active:
        raise ApiError(403, "账号已被停用")
    user.hashed_password = hash_password(payload.new_password)
    user.token_version = int(user.token_version or 0) + 1
    # 能收到验证码，说明邮箱确实属于本人
    user.email_verified = True
    db.commit()
    ratelimit.reset(email)
    ratelimit.reset(user.username.lower())
    return ok(None, "密码已重设，请用新密码登录")
