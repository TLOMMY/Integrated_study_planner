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

    # ---- B：邮件、验证码、反馈通知
    # 邮件发送方式：smtp（真实发送）/ console（只写日志，开发用）/ memory（测试读取）；
    # 留空时配置了 SMTP_HOST 就用 smtp，否则 console
    MAIL_BACKEND: str = (_env("MAIL_BACKEND", default="") or "").lower()
    SMTP_HOST: str = _env("SMTP_HOST", default="")
    SMTP_PORT: int = int(_env("SMTP_PORT", default="465"))
    SMTP_USER: str = _env("SMTP_USER", default="")
    SMTP_PASSWORD: str = _env("SMTP_PASSWORD", default="")
    # 1 = SSL（465 端口）；0 = 先明文连接再 STARTTLS（587 端口）
    SMTP_SSL: bool = _env("SMTP_SSL", default="1").lower() in {"1", "true", "yes"}
    SMTP_FROM: str = _env("SMTP_FROM", default="")
    # 注册时是否必须填写邮箱验证码（默认关闭，演示与测试不受影响）
    REQUIRE_EMAIL_VERIFY: bool = _env("REQUIRE_EMAIL_VERIFY", default="0").lower() in {"1", "true", "yes"}
    # 同一邮箱每天最多发送的验证码数量
    EMAIL_CODE_DAILY_LIMIT: int = int(_env("EMAIL_CODE_DAILY_LIMIT", default="10"))
    # 新反馈通知：群机器人地址（企业微信 / 飞书 / 钉钉，自动识别）、钉钉加签密钥、通知邮箱（逗号分隔）。
    # 管理后台「设置」里填写的值优先于这里
    FEEDBACK_WEBHOOK: str = _env("FEEDBACK_WEBHOOK", default="")
    FEEDBACK_WEBHOOK_SECRET: str = _env("FEEDBACK_WEBHOOK_SECRET", default="")
    FEEDBACK_NOTIFY_EMAILS: str = _env("FEEDBACK_NOTIFY_EMAILS", default="")
    # 网站对外地址（通知消息里的"后台链接"），如 https://app.xueyeguanjia.com
    APP_PUBLIC_URL: str = _env("APP_PUBLIC_URL", default="")

    # ---- F：联网搜索（AI 智能体推荐课程 / 学习资源时调用，见 app/ai/search.py）
    # AI_WEB_SEARCH=0 关闭全部联网搜索工具（B 站 + 通用搜索）
    AI_WEB_SEARCH: bool = _env("AI_WEB_SEARCH", default="1").lower() in {"1", "true", "yes"}
    # 通用搜索服务商：bocha（博查）/ tavily / serper；留空则依次尝试免 Key 的 360 搜索、必应、DuckDuckGo 网页结果（可能不稳定）
    SEARCH_PROVIDER: str = (_env("SEARCH_PROVIDER", default="") or "").strip().lower()
    SEARCH_API_KEY: Optional[str] = _env("SEARCH_API_KEY")
    SEARCH_TIMEOUT: int = int(_env("SEARCH_TIMEOUT", default="8"))


settings = Settings()

DEFAULT_SECRET = "dev-only-secret-change-me"
