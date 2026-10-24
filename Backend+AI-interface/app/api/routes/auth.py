# -*- coding: utf-8 -*-
from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core import ratelimit
from app.core.config import settings
from app.core.errors import ApiError, ok
from app.core.security import hash_password, token_payload, verify_password
from app.models import User
from app.schemas import LoginIn, RegisterIn
from app.services import schedule
from app.services.accounts import user_to_dict

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", summary="注册（成功后直接返回登录凭证）")
def register(payload: RegisterIn, db: DB):
    email = payload.email.lower()
    username = payload.username or email
    if db.query(User.id).filter(User.email == email).first():
        raise ApiError(400, "该邮箱已注册，请直接登录")
    if db.query(User.id).filter(User.username == username).first():
        raise ApiError(400, "用户名已被占用")
    user = User(
        username=username,
        email=email,
        full_name=payload.full_name or email.split("@")[0],
        avatar="🦉",
        hashed_password=hash_password(payload.password),
        semester=schedule.guess_semester(),
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
    return ok({**token_payload(user), "user": user_to_dict(user)}, "已进入演示账号")
