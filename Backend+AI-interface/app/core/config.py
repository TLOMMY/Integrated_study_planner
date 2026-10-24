# -*- coding: utf-8 -*-
"""
应用配置。

启动时读取项目根目录的 .env（进程环境变量优先），并兼容旧版变量名。
"""

import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", override=False)


def _env(*names: str, default: Optional[str] = None) -> Optional[str]:
    """按顺序取第一个非空的环境变量，兼容历史遗留的变量名。"""
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


def _resolve_sqlite_url(url: str) -> str:
    """把相对路径的 SQLite 地址固定到项目根目录，避免随启动目录变化而换库。"""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    raw_path = url[len(prefix):]
    if raw_path == ":memory:" or Path(raw_path).is_absolute():
        return url
    return f"{prefix}{(BASE_DIR / raw_path).resolve().as_posix()}"


class Settings:
    APP_NAME = "智能学习规划系统"
    APP_VERSION = "3.0.0"

    DATABASE_URL: str = _resolve_sqlite_url(_env("DATABASE_URL", default="sqlite:///./study_planner.db"))

    SECRET_KEY: str = _env("JWT_SECRET_KEY", "SECRET_KEY", default="dev-only-secret-change-me")
    ALGORITHM: str = _env("JWT_ALGORITHM", "ALGORITHM", default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        _env("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "ACCESS_TOKEN_EXPIRE_MINUTES", default="1440")
    )

    DEEPSEEK_API_KEY: Optional[str] = _env("DEEPSEEK_API_KEY")
    DEEPSEEK_API_URL: str = _env("DEEPSEEK_API_URL", default="https://api.deepseek.com/chat/completions")
    DEEPSEEK_MODEL: str = _env("DEEPSEEK_MODEL", default="deepseek-chat")
    DEEPSEEK_TIMEOUT: int = int(_env("DEEPSEEK_TIMEOUT", default="45"))

    # 用户自定义模型的超时；以及是否允许填写本机/内网地址（本地 Ollama 需要）。
    # 公网部署时建议设为 0，防止服务器被当作跳板访问内网。
    AI_TIMEOUT: int = int(_env("AI_TIMEOUT", default="45"))
    AI_ALLOW_PRIVATE_URLS: bool = _env("AI_ALLOW_PRIVATE_URLS", default="1").lower() in {"1", "true", "yes"}

    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in _env(
            "CORS_ORIGINS",
            # 后三个是安卓 / iOS App 外壳的页面来源（Capacitor）
            default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,https://localhost,http://localhost,capacitor://localhost",
        ).split(",")
        if origin.strip()
    ]

    # 是否在启动时创建演示账号与演示同学（排行榜用）
    SEED_DEMO: bool = _env("SEED_DEMO", default="1").lower() in {"1", "true", "yes"}

    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024

    # 用户反馈以 txt 保存的目录（已加入 .gitignore）；ADMIN_EMAILS 中的账号可在接口里查看反馈
    FEEDBACK_DIR: Path = Path(_env("FEEDBACK_DIR", default=str(BASE_DIR / "feedback")))
    ADMIN_EMAILS: List[str] = [e.strip().lower() for e in _env("ADMIN_EMAILS", default="").split(",") if e.strip()]

    # 登录防爆破：同一账号 10 分钟内连续失败 5 次锁定 10 分钟
    LOGIN_MAX_FAILS: int = int(_env("LOGIN_MAX_FAILS", default="5"))
    LOGIN_LOCK_MINUTES: int = int(_env("LOGIN_LOCK_MINUTES", default="10"))


settings = Settings()

DEFAULT_SECRET = "dev-only-secret-change-me"
