# -*- coding: utf-8 -*-
"""
管理后台：反馈处理、用户管理、数据看板、前端错误、系统设置；以及前端错误上报 POST /client-errors。

除 /client-errors 外，所有接口都要求管理员（User.is_admin 或邮箱在 .env 的 ADMIN_EMAILS 中）。
"""

import hashlib
import re
import secrets
from collections import defaultdict
from datetime import timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy import func, or_, select

from app.api.deps import DB
from app.core import ratelimit, timeutil
from app.core.config import settings
from app.core.errors import ApiError, ok
from app.core.security import get_optional_user, hash_password, require_admin
from app.models import (
    ChatConversation, ChatMessage, ClientError, Feedback, FocusRecord, StudyPlan, StudyTask, Timetable, User, XpEvent,
)
from app.schemas import AdminSettingsIn, AdminUserUpdateIn, ClientErrorIn, FeedbackReplyIn, FeedbackStatusIn
from app.services import mail, notify
from app.api.routes.feedback import STATUS_LABELS, feedback_to_dict

# 不设 prefix：本模块内的路径写完整（如 /admin/feedback），由 main.py 统一注册
router = APIRouter(tags=["管理后台"])

Admin = Annotated[User, Depends(require_admin)]


def _page(page: int, size: int) -> tuple[int, int]:
    return max(1, page), max(1, min(size, 100))


def _iso(value) -> Optional[str]:
    return value.isoformat() if value else None


def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# ---------------------------------------------------------------- 反馈
@router.get("/admin/feedback", summary="反馈列表（按状态 / 类型 / 关键词筛选，分页）")
def admin_feedback_list(_admin: Admin, db: DB, status: str = "", category: str = "", q: str = "", page: int = 1, size: int = 20):
    page, size = _page(page, size)
    query = db.query(Feedback)
    if status:
        query = query.filter(Feedback.status == status)
    if category:
        query = query.filter(Feedback.category == category)
    q = q.strip()
    if q:
        pattern = _like(q)
        select_user_ids = select(User.id).where(
            or_(User.email.ilike(pattern, escape="\\"), User.full_name.ilike(pattern, escape="\\"))
        )
        conditions = [Feedback.content.ilike(pattern, escape="\\"), Feedback.page.ilike(pattern, escape="\\"),
                      Feedback.user_id.in_(select_user_ids)]
        if q.lstrip("#").isdigit():
            conditions.append(Feedback.id == int(q.lstrip("#")))
        query = query.filter(or_(*conditions))
    total = query.count()
    rows = query.order_by(Feedback.id.desc()).offset((page - 1) * size).limit(size).all()
    owners = {u.id: u for u in db.query(User).filter(User.id.in_({r.user_id for r in rows if r.user_id})).all()} if rows else {}
    counts = dict(db.query(Feedback.status, func.count(Feedback.id)).group_by(Feedback.status).all())
    return ok({
        "items": [feedback_to_dict(r, owners.get(r.user_id), admin=True) for r in rows],
        "total": total,
        "page": page,
        "size": size,
        "counts": {key: int(counts.get(key, 0)) for key in STATUS_LABELS},
    })


def _feedback_or_404(db, feedback_id: int) -> Feedback:
    item = db.get(Feedback, feedback_id)
    if item is None:
        raise ApiError(404, "反馈不存在")
    return item


def _feedback_detail(db, item: Feedback) -> dict:
    owner = db.get(User, item.user_id) if item.user_id else None
    data = feedback_to_dict(item, owner, admin=True)
    if owner is not None:
        data["user"]["created_at"] = _iso(owner.created_at)
        data["user"]["last_seen_at"] = _iso(owner.last_seen_at)
        data["user"]["feedback_count"] = db.query(Feedback.id).filter(Feedback.user_id == owner.id).count()
    replier = db.get(User, item.replied_by) if item.replied_by else None
    data["replied_by_name"] = (replier.full_name or replier.username) if replier else ""
    return data


@router.get("/admin/feedback/{feedback_id}", summary="反馈详情（含截图与用户信息）")
def admin_feedback_detail(feedback_id: int, _admin: Admin, db: DB):
    return ok(_feedback_detail(db, _feedback_or_404(db, feedback_id)))


@router.put("/admin/feedback/{feedback_id}/status", summary="修改反馈状态（open / processing / resolved / closed）")
def admin_feedback_status(feedback_id: int, payload: FeedbackStatusIn, _admin: Admin, db: DB):
    item = _feedback_or_404(db, feedback_id)
    item.status = payload.status
    db.commit()
    return ok(_feedback_detail(db, item), f"已标记为「{STATUS_LABELS[payload.status]}」")


@router.post("/admin/feedback/{feedback_id}/reply", summary="回复反馈（用户在「我的反馈」里看到，可同时发邮件）")
def admin_feedback_reply(feedback_id: int, payload: FeedbackReplyIn, admin: Admin, db: DB, background: BackgroundTasks):
    item = _feedback_or_404(db, feedback_id)
    item.reply = payload.reply
    item.replied_at = timeutil.now()
    item.replied_by = admin.id
    item.user_unread = True
    if payload.status:
        item.status = payload.status
    elif item.status == "open":
        item.status = "processing"
    db.commit()
    owner = db.get(User, item.user_id) if item.user_id else None
    emailed = False
    if payload.send_email and owner is not None and not owner.is_demo and owner.email:
        summary = " ".join(item.content.split())[:80]
        text = (
            f"你好，{owner.full_name or owner.username}：\n\n你提交的反馈 #{item.id}「{summary}」有了回复：\n\n{payload.reply}\n\n"
            f"当前状态：{STATUS_LABELS.get(item.status, item.status)}。也可以在 App 的「设置 → 我的反馈」中查看。\n\n—— {settings.APP_NAME}"
        )
        background.add_task(notify.mail_reply_to_user, owner.email, f"【学业管家】你的反馈 #{item.id} 有了回复", text)
        emailed = True
    return ok({**_feedback_detail(db, item), "emailed": emailed}, "已回复，并已发送邮件" if emailed else "已回复，用户会在「我的反馈」看到")


# ---------------------------------------------------------------- 用户
def _user_row(user: User, tasks: dict, focus: dict) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "name": user.full_name or user.username,
        "avatar": user.avatar or "🦉",
        "is_active": bool(user.is_active),
        "is_admin": bool(user.is_admin) or (user.email or "").lower() in settings.ADMIN_EMAILS,
        "admin_by_env": (user.email or "").lower() in settings.ADMIN_EMAILS,
        "is_demo": bool(user.is_demo),
        "email_verified": bool(user.email_verified),
        "created_at": _iso(user.created_at),
        "last_seen_at": _iso(user.last_seen_at),
        "task_count": int(tasks.get(user.id, 0)),
        "focus_minutes": int(focus.get(user.id, 0)),
    }


def _user_stats(db, ids) -> tuple[dict, dict]:
    if not ids:
        return {}, {}
    tasks = dict(db.query(StudyTask.user_id, func.count(StudyTask.id)).filter(StudyTask.user_id.in_(ids)).group_by(StudyTask.user_id).all())
    focus = dict(
        db.query(FocusRecord.user_id, func.coalesce(func.sum(FocusRecord.duration_minutes), 0))
        .filter(FocusRecord.user_id.in_(ids)).group_by(FocusRecord.user_id).all()
    )
    return tasks, focus


@router.get("/admin/users", summary="用户列表（搜索邮箱 / 昵称 / 编号，按状态筛选）")
def admin_users(_admin: Admin, db: DB, q: str = "", status: str = "", page: int = 1, size: int = 20):
    page, size = _page(page, size)
    query = db.query(User)
    q = q.strip()
    if q:
        pattern = _like(q)
        conditions = [User.email.ilike(pattern, escape="\\"), User.full_name.ilike(pattern, escape="\\"),
                      User.username.ilike(pattern, escape="\\")]
        if q.lstrip("#").isdigit():
            conditions.append(User.id == int(q.lstrip("#")))
        query = query.filter(or_(*conditions))
    if status == "active":
        query = query.filter(User.is_active.is_(True))
    elif status == "disabled":
        query = query.filter(User.is_active.is_(False))
    elif status == "admin":
        query = query.filter(or_(User.is_admin.is_(True), func.lower(User.email).in_(settings.ADMIN_EMAILS or [""])))
    total = query.count()
    rows = query.order_by(User.id.desc()).offset((page - 1) * size).limit(size).all()
    tasks, focus = _user_stats(db, [u.id for u in rows])
    return ok({"items": [_user_row(u, tasks, focus) for u in rows], "total": total, "page": page, "size": size})


def _user_or_404(db, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "用户不存在")
    return user


def _user_detail(db, user: User) -> dict:
    tasks, focus = _user_stats(db, [user.id])
    data = _user_row(user, tasks, focus)
    since = (timeutil.today() - timedelta(days=29)).isoformat()
    data.update(
        completed_tasks=db.query(StudyTask.id).filter(StudyTask.user_id == user.id, StudyTask.completed.is_(True)).count(),
        plan_count=db.query(StudyPlan.id).filter(StudyPlan.user_id == user.id).count(),
        course_count=db.query(Timetable.id).filter(Timetable.user_id == user.id).count(),
        focus_sessions=db.query(FocusRecord.id).filter(FocusRecord.user_id == user.id).count(),
        xp_total=int(db.query(func.coalesce(func.sum(XpEvent.amount), 0)).filter(XpEvent.user_id == user.id).scalar() or 0),
        ai_messages=db.query(ChatMessage.id).filter(ChatMessage.user_id == user.id, ChatMessage.role == "user").count(),
        feedback_count=db.query(Feedback.id).filter(Feedback.user_id == user.id).count(),
        active_days_30=len([d for d in (user.active_days or "").split(",") if d and d >= since]),
        semester=user.semester or "",
        phone_masked=f"{user.phone[:3]}****{user.phone[-4:]}" if user.phone else "",
    )
    return data


@router.get("/admin/users/{user_id}", summary="用户概况（注册时间、最近活跃、任务数、专注时长等）")
def admin_user_detail(user_id: int, _admin: Admin, db: DB):
    return ok(_user_detail(db, _user_or_404(db, user_id)))


@router.put("/admin/users/{user_id}", summary="停用 / 启用账号，设为 / 取消管理员")
def admin_user_update(user_id: int, payload: AdminUserUpdateIn, admin: Admin, db: DB):
    user = _user_or_404(db, user_id)
    messages = []
    if payload.is_active is not None and bool(user.is_active) != payload.is_active:
        if user.id == admin.id:
            raise ApiError(400, "不能停用自己的账号")
        user.is_active = payload.is_active
        messages.append("账号已启用" if payload.is_active else "账号已停用，该用户将无法登录")
    if payload.is_admin is not None:
        by_env = (user.email or "").lower() in settings.ADMIN_EMAILS
        if not payload.is_admin and user.id == admin.id:
            raise ApiError(400, "不能取消自己的管理员身份")
        if not payload.is_admin and by_env:
            raise ApiError(400, "该账号在服务器配置 ADMIN_EMAILS 中，需修改配置后才能取消")
        if bool(user.is_admin) != payload.is_admin:
            if payload.is_admin and user.is_demo:
                raise ApiError(400, "演示账号不能设为管理员")
            user.is_admin = payload.is_admin
            messages.append("已设为管理员" if payload.is_admin else "已取消管理员")
    db.commit()
    db.refresh(user)
    return ok(_user_detail(db, user), "，".join(messages) or "没有变化")


TEMP_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@router.post("/admin/users/{user_id}/reset-password", summary="重置密码：生成临时密码（只显示一次），该用户所有登录失效")
def admin_reset_password(user_id: int, admin: Admin, db: DB):
    user = _user_or_404(db, user_id)
    if user.id == admin.id:
        raise ApiError(400, "请在「设置 → 修改密码」里修改自己的密码")
    if user.is_demo:
        raise ApiError(400, "演示账号不能重置密码")
    temp = "".join(secrets.choice(TEMP_ALPHABET) for _ in range(10))
    user.hashed_password = hash_password(temp)
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    ratelimit.reset((user.email or "").lower())
    ratelimit.reset((user.username or "").lower())
    return ok({"temp_password": temp, "email": user.email}, "已生成临时密码，请转告用户登录后尽快修改")


# ---------------------------------------------------------------- 看板
@router.get("/admin/dashboard", summary="数据看板：注册、日活/周活、近 14 天趋势、AI 对话、反馈、前端错误")
def admin_dashboard(_admin: Admin, db: DB):
    today = timeutil.today()
    since30 = today - timedelta(days=29)

    # 活跃：当天有学习行为（经验记录）或打开过 App（active_days）；演示账号与演示同学一律不计
    real_ids = select(User.id).where(User.is_demo.is_(False))
    active = defaultdict(set)
    for uid, day in db.query(XpEvent.user_id, XpEvent.event_date).filter(
        XpEvent.event_date >= since30, XpEvent.reason != "seed", XpEvent.user_id.in_(real_ids)
    ).distinct():
        active[day.isoformat()].add(uid)
    for uid, raw in db.query(User.id, User.active_days).filter(User.active_days.isnot(None), User.is_demo.is_(False)):
        for day in raw.split(","):
            if day and day >= since30.isoformat():
                active[day].add(uid)

    def active_in(days: int) -> int:
        start = (today - timedelta(days=days - 1)).isoformat()
        return len(set().union(*[ids for day, ids in active.items() if day >= start] or [set()]))

    since14 = today - timedelta(days=13)
    start14 = timeutil.combine(since14, "00:00")
    registered = defaultdict(int)
    for (created,) in db.query(User.created_at).filter(User.created_at >= start14, User.is_demo.is_(False)):
        registered[created.date().isoformat()] += 1
    chats = defaultdict(int)
    for (created,) in db.query(ChatMessage.created_at).filter(ChatMessage.role == "user", ChatMessage.created_at >= start14):
        chats[created.date().isoformat()] += 1
    trend = []
    for offset in range(14):
        day = (since14 + timedelta(days=offset)).isoformat()
        trend.append({"date": day, "label": day[5:], "new_users": registered[day], "active_users": len(active.get(day, ())),
                      "ai_messages": chats[day]})

    week_ago = timeutil.now() - timedelta(days=7)
    feedback_counts = dict(db.query(Feedback.status, func.count(Feedback.id)).group_by(Feedback.status).all())
    real_users = db.query(User.id).filter(User.is_demo.is_(False))
    return ok({
        "users": {
            "total": real_users.count(),
            "demo": db.query(User.id).filter(User.is_demo.is_(True)).count(),
            "disabled": db.query(User.id).filter(User.is_active.is_(False)).count(),
            "new_today": registered[today.isoformat()],
            "new_7d": sum(v for d, v in registered.items() if d >= (today - timedelta(days=6)).isoformat()),
            "dau": active_in(1),
            "wau": active_in(7),
            "mau": active_in(30),
        },
        "ai": {
            "messages_total": db.query(ChatMessage.id).filter(ChatMessage.role == "user").count(),
            "messages_today": chats[today.isoformat()],
            "messages_7d": sum(v for d, v in chats.items() if d >= (today - timedelta(days=6)).isoformat()),
            "conversations": db.query(ChatConversation.id).count(),
        },
        "feedback": {
            "total": sum(int(v) for v in feedback_counts.values()),
            "by_status": {key: int(feedback_counts.get(key, 0)) for key in STATUS_LABELS},
            "new_7d": db.query(Feedback.id).filter(Feedback.created_at >= week_ago).count(),
        },
        "errors": {
            "groups": db.query(ClientError.id).count(),
            "groups_7d": db.query(ClientError.id).filter(ClientError.last_seen >= week_ago).count(),
            "occurrences_7d": int(db.query(func.coalesce(func.sum(ClientError.count), 0)).filter(ClientError.last_seen >= week_ago).scalar() or 0),
        },
        "trend": trend,
    })


# ---------------------------------------------------------------- 前端错误
def _first_frame(stack: str, message: str) -> str:
    """堆栈里第一条调用位置（跳过与消息相同的首行），用于生成指纹。"""
    for line in (stack or "").splitlines():
        line = line.strip()
        if not line or message[:60] in line:
            continue
        # 去掉行号列号之外的查询串（如 ?v=123），同一位置的错误归为一组
        return re.sub(r"\?[^:)\s]*", "", line)[:300]
    return ""


def error_fingerprint(message: str, stack: str) -> str:
    return hashlib.sha256(f"{message.strip()[:300]}\n{_first_frame(stack, message.strip())}".encode("utf-8")).hexdigest()[:40]


@router.post("/client-errors", summary="前端运行时错误上报（登录可选，按 message + 堆栈首行聚合计数）")
def report_client_error(payload: ClientErrorIn, request: Request, db: DB, user: Optional[User] = Depends(get_optional_user)):
    if not ratelimit.hit("client-error", ratelimit.client_ip(request), 30, 60):
        raise ApiError(429, "上报太频繁")
    message = payload.message.strip()
    stack = (payload.stack or "").strip()
    if payload.info:
        stack = f"{stack}\n[vue] {payload.info}".strip()
    fingerprint = error_fingerprint(message, payload.stack or "")
    now = timeutil.now()
    client = (payload.client or request.headers.get("user-agent", ""))[:300]
    row = db.query(ClientError).filter(ClientError.fingerprint == fingerprint).first()
    if row is None:
        row = ClientError(fingerprint=fingerprint, message=message[:500], stack=stack[:8000] or None, count=1,
                          created_at=now, last_seen=now)
        db.add(row)
    else:
        row.count = int(row.count or 0) + 1
        row.last_seen = now
        if stack and not row.stack:
            row.stack = stack[:8000]
    row.user_id = user.id if user else row.user_id
    row.page = (payload.page or "")[:200] or row.page
    row.client = client or row.client
    row.app_version = (payload.version or "")[:20] or row.app_version
    db.commit()
    return ok({"fingerprint": fingerprint, "count": row.count}, "已记录")


@router.get("/admin/errors", summary="前端错误（按指纹聚合，次数、最近出现、页面、版本）")
def admin_errors(_admin: Admin, db: DB, q: str = "", days: int = 30, page: int = 1, size: int = 20):
    page, size = _page(page, size)
    query = db.query(ClientError).filter(ClientError.last_seen >= timeutil.now() - timedelta(days=max(1, min(days, 365))))
    if q.strip():
        pattern = _like(q.strip())
        query = query.filter(or_(ClientError.message.ilike(pattern, escape="\\"), ClientError.page.ilike(pattern, escape="\\")))
    total = query.count()
    rows = query.order_by(ClientError.last_seen.desc(), ClientError.id.desc()).offset((page - 1) * size).limit(size).all()
    items = [
        {"id": r.id, "message": r.message, "stack": r.stack or "", "page": r.page or "", "client": r.client or "",
         "version": r.app_version or "", "count": int(r.count or 0), "user_id": r.user_id, "fingerprint": r.fingerprint,
         "first_seen": _iso(r.created_at), "last_seen": _iso(r.last_seen)}
        for r in rows
    ]
    return ok({"items": items, "total": total, "page": page, "size": size})


@router.delete("/admin/errors/{error_id}", summary="删除一组错误（已修复）")
def admin_error_delete(error_id: int, _admin: Admin, db: DB):
    row = db.get(ClientError, error_id)
    if row is None:
        raise ApiError(404, "记录不存在")
    db.delete(row)
    db.commit()
    return ok(None, "已删除")


# ---------------------------------------------------------------- 设置
def _mask(value: str) -> str:
    if not value:
        return ""
    match = re.match(r"^(https?://[^/]+)", value)
    if match:
        return f"{match.group(1)}/…{value[-4:]}"
    return f"{'•' * 6}{value[-4:]}" if len(value) > 8 else "•" * 6


def _settings_view(db) -> dict:
    config = notify.load_config(db)

    def source(key: str, env_value: str) -> str:
        if notify.get_setting(db, key) is not None:
            return "admin"
        return "env" if env_value else "none"

    return {
        "feedback_webhook_masked": _mask(config["webhook"]),
        "feedback_webhook_set": bool(config["webhook"]),
        "feedback_webhook_kind": notify.KIND_LABELS[notify.detect_kind(config["webhook"])] if config["webhook"] else "",
        "feedback_webhook_secret_masked": _mask(config["secret"]),
        "feedback_webhook_secret_set": bool(config["secret"]),
        "feedback_notify_emails": ",".join(config["emails"]),
        "public_url": config["public_url"],
        "source": {
            "feedback_webhook": source(notify.KEY_WEBHOOK, settings.FEEDBACK_WEBHOOK),
            "feedback_webhook_secret": source(notify.KEY_SECRET, settings.FEEDBACK_WEBHOOK_SECRET),
            "feedback_notify_emails": source(notify.KEY_EMAILS, settings.FEEDBACK_NOTIFY_EMAILS),
            "public_url": source(notify.KEY_PUBLIC_URL, settings.APP_PUBLIC_URL),
        },
        "mail_backend": mail.backend(),
        "mail_enabled": mail.can_deliver(),
        "require_email_verify": settings.REQUIRE_EMAIL_VERIFY,
    }


@router.get("/admin/settings", summary="系统设置：反馈通知（机器人地址与密钥只返回掩码）")
def admin_settings(_admin: Admin, db: DB):
    return ok(_settings_view(db))


@router.put("/admin/settings", summary="保存系统设置（不传的字段保持不变，传空串表示清空）")
def admin_settings_save(payload: AdminSettingsIn, _admin: Admin, db: DB):
    mapping = {
        "feedback_webhook": notify.KEY_WEBHOOK,
        "feedback_webhook_secret": notify.KEY_SECRET,
        "feedback_notify_emails": notify.KEY_EMAILS,
        "public_url": notify.KEY_PUBLIC_URL,
    }
    for field, value in payload.model_dump(exclude_none=True).items():
        notify.set_setting(db, mapping[field], value.rstrip("/") if field == "public_url" else value)
    db.commit()
    return ok(_settings_view(db), "设置已保存")


@router.post("/admin/settings/test-notify", summary="按当前设置发送一条测试通知")
def admin_test_notify(admin: Admin, db: DB):
    config = notify.load_config(db)
    if not config["webhook"] and not config["emails"]:
        raise ApiError(400, "还没有配置机器人地址或通知邮箱")
    text = f"这是一条测试通知，说明反馈通知配置正确。\n发送人：{admin.full_name or admin.username}\n时间：{timeutil.now():%Y-%m-%d %H:%M:%S}"
    result = notify.send(db, "【学业管家】测试通知", text)
    failed = [f"{'机器人' if k == 'webhook' else '邮件'}：{v}" for k, v in result.items() if v and v != "ok"]
    if failed and not any(v == "ok" for v in result.values()):
        raise ApiError(502, "；".join(failed), result)
    return ok(result, "测试通知已发送" + (f"（部分失败：{'；'.join(failed)}）" if failed else ""))

