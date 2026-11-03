# -*- coding: utf-8 -*-
"""
AI 用量限额：只限制使用服务器 DeepSeek Key（ModelConfig.source == "env"）的请求；用户自己的 Key、管理员不受限。

挂钩方式（集中在模型配置解析与 llm 客户端两处，所有 AI 入口自动覆盖）：
  1. providers.resolve() 返回服务器配置时调用 attach()，给配置打上 quota_ticket="<user_id>:<随机串>"；
  2. llm.chat() / llm.stream_chat() 发请求前后调用本模块注册的钩子：
       check  —— 该凭据第一次调用前检查今日次数与 token，超额抛 429（之后的多步工具调用不再检查，避免回复到一半被打断）；
       start  —— 请求成功后，同一凭据只记 1 次（一次对话回合里多步工具调用算一次）；
       usage  —— 记录本次返回的 token（流式结果里有 usage 时）。
上限默认取配置 AI_DAILY_CALLS / AI_DAILY_TOKENS，管理后台「设置」里改的值（AppSetting）优先；0 表示不限。
"""

import logging
import secrets
import threading
from collections import OrderedDict
from datetime import timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai import llm
from app.core import timeutil
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import ApiError
from app.models import AiUsage, AppSetting, User

logger = logging.getLogger("study_planner.ai_quota")

KEY_CALLS = "ai_daily_calls"
KEY_TOKENS = "ai_daily_tokens"

_lock = threading.Lock()
# 已计数的凭据（进程内，最多保留最近 5000 个）
_seen: "OrderedDict[str, bool]" = OrderedDict()
_checked: "OrderedDict[str, bool]" = OrderedDict()
_MAX_TICKETS = 5000


# ---------------------------------------------------------------- 上限
def _setting_int(db: Session, key: str, fallback: int) -> int:
    row = db.get(AppSetting, key)
    if row is None or row.value in (None, ""):
        return max(0, int(fallback))
    try:
        return max(0, int(row.value))
    except ValueError:
        return max(0, int(fallback))


def limits(db: Session) -> dict:
    """{"calls": 每日次数上限, "tokens": 每日 token 上限}，0 = 不限。"""
    return {"calls": _setting_int(db, KEY_CALLS, settings.AI_DAILY_CALLS),
            "tokens": _setting_int(db, KEY_TOKENS, settings.AI_DAILY_TOKENS)}


def limit_sources(db: Session) -> dict:
    return {"calls": "admin" if db.get(AppSetting, KEY_CALLS) is not None else "env",
            "tokens": "admin" if db.get(AppSetting, KEY_TOKENS) is not None else "env"}


def set_limits(db: Session, calls: Optional[int] = None, tokens: Optional[int] = None) -> None:
    """管理后台保存上限（调用方 commit）。"""
    for key, value in ((KEY_CALLS, calls), (KEY_TOKENS, tokens)):
        if value is None:
            continue
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=str(int(value))))
        else:
            row.value = str(int(value))


# ---------------------------------------------------------------- 用量
def _today() -> str:
    return timeutil.today().isoformat()


def usage_today(db: Session, user_id: int) -> dict:
    row = db.query(AiUsage).filter(AiUsage.user_id == user_id, AiUsage.day == _today()).first()
    return {"calls": int(row.calls or 0) if row else 0, "tokens": int(row.total_tokens or 0) if row else 0}


def _exempt(user: Optional[User]) -> bool:
    from app.core.security import is_admin_user

    return is_admin_user(user)


def status(db: Session, user: User) -> dict:
    """今日用量与剩余次数（给 AI 页、设置页显示）。"""
    lim = limits(db)
    used = usage_today(db, user.id)
    exempt = _exempt(user)
    limited = not exempt and (lim["calls"] > 0 or lim["tokens"] > 0)
    calls_left = max(0, lim["calls"] - used["calls"]) if limited and lim["calls"] else None
    tokens_left = max(0, lim["tokens"] - used["tokens"]) if limited and lim["tokens"] else None
    exceeded = limited and (calls_left == 0 or tokens_left == 0)
    return {
        "limited": limited,
        "exempt": exempt,
        "calls_used": used["calls"],
        "calls_limit": lim["calls"] or None,
        "calls_left": calls_left,
        "tokens_used": used["tokens"],
        "tokens_limit": lim["tokens"] or None,
        "tokens_left": tokens_left,
        "exceeded": exceeded,
        "resets_at": (timeutil.combine(timeutil.today() + timedelta(days=1), "00:00")).isoformat(),
    }


EXCEEDED_MESSAGE = ("今天的服务器 AI 额度已用完（{detail}），明天 0 点恢复。"
                    "可以在「AI 设置」中添加自己的模型 Key 继续使用，或切换到本地规则引擎（不限次数）")


def exceeded_error(state: dict) -> ApiError:
    if state["calls_left"] == 0:
        detail = f"每天 {state['calls_limit']} 次"
    else:
        detail = f"每天 {state['tokens_limit']:,} tokens"
    return ApiError(429, EXCEEDED_MESSAGE.format(detail=detail), {"reason": "ai_quota", "quota": state})


def ensure_available(db: Session, user: User) -> None:
    """超额时抛 429（对话接口在保存消息前先检查，避免返回 200 的事件流里才报错）。"""
    state = status(db, user)
    if state["exceeded"]:
        raise exceeded_error(state)


# ---------------------------------------------------------------- 凭据
def attach(config: Optional[llm.ModelConfig], user: Optional[User]) -> Optional[llm.ModelConfig]:
    """服务器配置打上本次操作的计数凭据；用户自己的配置、管理员原样返回。"""
    if config is None or config.source != "env" or user is None or getattr(user, "id", None) is None:
        return config
    if _exempt(user):
        return config
    config.quota_ticket = f"{user.id}:{secrets.token_hex(8)}"
    return config


def _remember(store: OrderedDict, ticket: str) -> bool:
    """第一次见到该凭据返回 True。"""
    with _lock:
        if ticket in store:
            return False
        store[ticket] = True
        while len(store) > _MAX_TICKETS:
            store.popitem(last=False)
        return True


def _bump(user_id: int, calls: int = 0, usage: Optional[dict] = None) -> None:
    usage = usage or {}

    def number(key: str) -> int:
        value = usage.get(key)
        return int(value) if isinstance(value, (int, float)) and value > 0 else 0

    prompt, completion = number("prompt_tokens"), number("completion_tokens")
    total = number("total_tokens") or prompt + completion
    if not calls and not total:
        return
    db = SessionLocal()
    try:
        for _attempt in range(2):
            row = db.query(AiUsage).filter(AiUsage.user_id == user_id, AiUsage.day == _today()).first()
            if row is None:
                row = AiUsage(user_id=user_id, day=_today(), calls=0, prompt_tokens=0, completion_tokens=0, total_tokens=0)
                db.add(row)
            row.calls = int(row.calls or 0) + calls
            row.prompt_tokens = int(row.prompt_tokens or 0) + prompt
            row.completion_tokens = int(row.completion_tokens or 0) + completion
            row.total_tokens = int(row.total_tokens or 0) + total
            try:
                db.commit()
                return
            except IntegrityError:  # 并发时另一个请求刚插入了当天的行：重读后累加
                db.rollback()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("记录 AI 用量失败（不影响本次回复）")
    finally:
        db.close()


def _user_id(ticket: str) -> Optional[int]:
    head = (ticket or "").split(":", 1)[0]
    return int(head) if head.isdigit() else None


def _hook(stage: str, config: llm.ModelConfig, usage: Optional[dict] = None) -> None:
    ticket = getattr(config, "quota_ticket", None)
    if not ticket or config.source != "env":
        return
    user_id = _user_id(ticket)
    if user_id is None:
        return
    if stage == "check":
        if not _remember(_checked, ticket):
            return
        db = SessionLocal()
        try:
            user = db.get(User, user_id)
            if user is None or _exempt(user):
                return
            state = status(db, user)
        finally:
            db.close()
        if state["exceeded"]:
            raise exceeded_error(state)
    elif stage == "start":
        if _remember(_seen, ticket):
            _bump(user_id, calls=1)
    elif stage == "usage":
        _bump(user_id, usage=usage)


llm.set_usage_hook(_hook)


# ---------------------------------------------------------------- 管理后台统计
def dashboard(db: Session, top: int = 10) -> dict:
    today = timeutil.today()
    since7 = (today - timedelta(days=6)).isoformat()

    def totals(day_from: str) -> dict:
        calls, tokens, users = db.query(
            func.coalesce(func.sum(AiUsage.calls), 0), func.coalesce(func.sum(AiUsage.total_tokens), 0),
            func.count(func.distinct(AiUsage.user_id)),
        ).filter(AiUsage.day >= day_from).one()
        return {"calls": int(calls or 0), "tokens": int(tokens or 0), "users": int(users or 0)}

    rows = (db.query(AiUsage.user_id, func.sum(AiUsage.calls).label("calls"), func.sum(AiUsage.total_tokens).label("tokens"))
            .filter(AiUsage.day >= since7).group_by(AiUsage.user_id)
            .order_by(func.sum(AiUsage.total_tokens).desc(), func.sum(AiUsage.calls).desc()).limit(top).all())
    names = {u.id: u for u in db.query(User).filter(User.id.in_([r.user_id for r in rows])).all()} if rows else {}
    today_rows = dict(db.query(AiUsage.user_id, AiUsage.calls).filter(AiUsage.day == today.isoformat()).all())
    top_users = [
        {"user_id": r.user_id,
         "name": (names[r.user_id].full_name or names[r.user_id].username) if r.user_id in names else f"#{r.user_id}",
         "email": names[r.user_id].email if r.user_id in names else "",
         "is_demo": bool(names[r.user_id].is_demo) if r.user_id in names else False,
         "calls_7d": int(r.calls or 0), "tokens_7d": int(r.tokens or 0), "calls_today": int(today_rows.get(r.user_id, 0) or 0)}
        for r in rows
    ]
    trend = {d: {"calls": 0, "tokens": 0} for d in ((today - timedelta(days=i)).isoformat() for i in range(6, -1, -1))}
    for day, calls, tokens in (db.query(AiUsage.day, func.sum(AiUsage.calls), func.sum(AiUsage.total_tokens))
                               .filter(AiUsage.day >= since7).group_by(AiUsage.day)):
        if day in trend:
            trend[day] = {"calls": int(calls or 0), "tokens": int(tokens or 0)}
    return {
        "today": totals(today.isoformat()),
        "last_7d": totals(since7),
        "limits": limits(db),
        "top_users": top_users,
        "trend": [{"date": d, "label": d[5:], **v} for d, v in trend.items()],
    }
