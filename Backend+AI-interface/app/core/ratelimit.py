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
        else:
            _fails.pop(key, None)
