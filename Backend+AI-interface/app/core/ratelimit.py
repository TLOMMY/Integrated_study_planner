# -*- coding: utf-8 -*-
"""
登录失败计数（进程内存）。

单进程部署足够；若以后多进程/多机部署，需要换成 Redis 等共享存储。
"""

import threading
import time
from typing import Dict, List

from app.core.config import settings

_lock = threading.Lock()
_fails: Dict[str, List[float]] = {}


def _window() -> float:
    return settings.LOGIN_LOCK_MINUTES * 60


def remaining_lock_seconds(key: str) -> int:
    """账号处于锁定期时返回剩余秒数，否则 0。"""
    now = time.monotonic()
    with _lock:
        recent = [t for t in _fails.get(key, []) if now - t < _window()]
        _fails[key] = recent
        if len(recent) < settings.LOGIN_MAX_FAILS:
            return 0
        return max(1, int(_window() - (now - recent[-1])))


def record_failure(key: str) -> int:
    """记一次失败，返回本窗口内还剩几次机会。"""
    now = time.monotonic()
    with _lock:
        recent = [t for t in _fails.get(key, []) if now - t < _window()]
        recent.append(now)
        _fails[key] = recent
        return max(0, settings.LOGIN_MAX_FAILS - len(recent))


def reset(key: str = None) -> None:
    with _lock:
        if key is None:
            _fails.clear()
            _hits.clear()
        else:
            _fails.pop(key, None)


# ---------------------------------------------------------------- 通用滑动窗口限流（验证码、错误上报、截图上传）
_hits: Dict[str, List[float]] = {}


def hit(bucket: str, key: str, limit: int, window_seconds: float) -> bool:
    """记一次请求；窗口内超过 limit 次返回 False（本次不计入）。"""
    now = time.monotonic()
    name = f"{bucket}:{key}"
    with _lock:
        recent = [t for t in _hits.get(name, []) if now - t < window_seconds]
        if len(recent) >= limit:
            _hits[name] = recent
            return False
        recent.append(now)
        _hits[name] = recent
        # 防止键无限增长：偶尔清理一次过期的键
        if len(_hits) > 5000:
            for stale in [k for k, v in _hits.items() if not v or now - v[-1] > 86400]:
                _hits.pop(stale, None)
        return True


def client_ip(request) -> str:
    """取客户端 IP（反向代理时读 X-Forwarded-For 的第一个）。"""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "") or "unknown"
