# -*- coding: utf-8 -*-
"""
登录失败计数与通用滑动窗口限流（存 SQLite 的 rate_events 表，服务重启后锁定与限流不丢失）。

接口与旧版（进程内存）保持一致：remaining_lock_seconds / record_failure / reset / hit / client_ip。
每次操作用独立的短连接（engine.begin()），不占用请求的数据库会话；
数据库暂时不可写（被锁）时放行请求并记日志，限流失败不能让登录等主流程报错。
单机部署足够；多机部署时需要换成共享存储（Redis 等）。
"""

import logging
import threading
import time
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import engine
from app.models.ops import RateEvent

logger = logging.getLogger("study_planner.ratelimit")

LOGIN_BUCKET = "login-fail"
# 超过这个时长的事件一律清理（最长的限流窗口是 1 天）
_KEEP_SECONDS = 2 * 86400
_PURGE_EVERY = 200

_lock = threading.Lock()
_ready_for: Optional[str] = None
_writes = 0
_table = RateEvent.__table__


def _ensure_table() -> None:
    """测试或脚本可能在应用启动（建表）之前调用，这里按需建表一次。"""
    global _ready_for
    url = str(engine.url)
    if _ready_for == url:
        return
    with _lock:
        if _ready_for != url:
            _table.create(bind=engine, checkfirst=True)
            _ready_for = url


def _now() -> float:
    # 墙上时间：需要跨进程 / 重启比较，不能用 monotonic
    return time.time()


def _key(value: str) -> str:
    return (value or "")[:200]


def _maybe_purge(conn, now: float) -> None:
    global _writes
    _writes += 1
    if _writes % _PURGE_EVERY == 0:
        conn.execute(delete(_table).where(_table.c.ts < now - _KEEP_SECONDS))


def _recent(conn, bucket: str, key: str, since: float):
    return conn.execute(
        select(func.count(), func.max(_table.c.ts))
        .where(_table.c.bucket == bucket, _table.c.key == key, _table.c.ts > since)
    ).one()


# ---------------------------------------------------------------- 通用计数（告警等也用）
def add(bucket: str, key: str = "") -> None:
    """记一次事件。"""
    _ensure_table()
    now = _now()
    with engine.begin() as conn:
        conn.execute(_table.insert().values(bucket=bucket, key=_key(key), ts=now))
        _maybe_purge(conn, now)


def count(bucket: str, key: str, window_seconds: float) -> int:
    """窗口内的事件数。"""
    _ensure_table()
    with engine.connect() as conn:
        return int(_recent(conn, bucket, _key(key), _now() - window_seconds)[0] or 0)


def clear(bucket: str, key: Optional[str] = None) -> None:
    _ensure_table()
    with engine.begin() as conn:
        condition = _table.c.bucket == bucket
        if key is not None:
            condition = condition & (_table.c.key == _key(key))
        conn.execute(delete(_table).where(condition))


# ---------------------------------------------------------------- 登录防爆破
def _window() -> float:
    return settings.LOGIN_LOCK_MINUTES * 60


def remaining_lock_seconds(key: str) -> int:
    """账号处于锁定期时返回剩余秒数，否则 0。"""
    try:
        _ensure_table()
        now = _now()
        with engine.connect() as conn:
            total, latest = _recent(conn, LOGIN_BUCKET, _key(key), now - _window())
    except SQLAlchemyError:
        logger.exception("读取登录失败次数出错，本次不锁定")
        return 0
    if int(total or 0) < settings.LOGIN_MAX_FAILS:
        return 0
    return max(1, int(_window() - (now - float(latest))))


def record_failure(key: str) -> int:
    """记一次失败，返回本窗口内还剩几次机会。"""
    try:
        add(LOGIN_BUCKET, key)
        recent = count(LOGIN_BUCKET, key, _window())
    except SQLAlchemyError:
        logger.exception("记录登录失败出错")
        return settings.LOGIN_MAX_FAILS
    return max(0, settings.LOGIN_MAX_FAILS - recent)


def reset(key: str = None) -> None:
    """key=None 清空全部计数（测试用）；否则只清除该账号的登录失败记录。"""
    try:
        _ensure_table()
        with engine.begin() as conn:
            if key is None:
                conn.execute(delete(_table))
            else:
                conn.execute(delete(_table).where(_table.c.bucket == LOGIN_BUCKET, _table.c.key == _key(key)))
    except SQLAlchemyError:
        logger.exception("清除限流记录出错")


# ---------------------------------------------------------------- 通用滑动窗口限流（验证码、错误上报、截图上传）
def hit(bucket: str, key: str, limit: int, window_seconds: float) -> bool:
    """记一次请求；窗口内超过 limit 次返回 False（本次不计入）。"""
    try:
        _ensure_table()
        now = _now()
        name = _key(key)
        with _lock, engine.begin() as conn:
            if int(_recent(conn, bucket, name, now - window_seconds)[0] or 0) >= limit:
                return False
            conn.execute(_table.insert().values(bucket=bucket, key=name, ts=now))
            _maybe_purge(conn, now)
            return True
    except SQLAlchemyError:
        logger.exception("限流计数出错，本次放行")
        return True


def client_ip(request) -> str:
    """取客户端 IP（反向代理时读 X-Forwarded-For 的第一个）。"""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "") or "unknown"
