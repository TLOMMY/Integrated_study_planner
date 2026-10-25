# -*- coding: utf-8 -*-
"""
新反馈通知：推送到群机器人（企业微信 / 飞书 / 钉钉，按地址自动识别格式）或发邮件给管理员。

配置优先级：管理后台「设置」（AppSetting 表）> .env（FEEDBACK_WEBHOOK、FEEDBACK_WEBHOOK_SECRET、FEEDBACK_NOTIFY_EMAILS）。
由 BackgroundTasks 在响应返回后发送，失败只记日志，不影响用户提交。
"""

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import AppSetting, Feedback, User
from app.services import mail

logger = logging.getLogger("study_planner.notify")

# AppSetting 中的键
KEY_WEBHOOK = "feedback_webhook"
KEY_SECRET = "feedback_webhook_secret"
KEY_EMAILS = "feedback_notify_emails"
KEY_PUBLIC_URL = "public_url"
SETTING_KEYS = (KEY_WEBHOOK, KEY_SECRET, KEY_EMAILS, KEY_PUBLIC_URL)

CATEGORY_LABELS = {"bug": "功能异常", "suggestion": "功能建议", "ui": "界面问题", "other": "其他"}
TIMEOUT = 8


# ---------------------------------------------------------------- 配置
def get_setting(db: Session, key: str) -> Optional[str]:
    row = db.get(AppSetting, key)
    return row.value if row is not None else None


def set_setting(db: Session, key: str, value: Optional[str]) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value


def load_config(db: Session) -> dict:
    """后台设置过（哪怕设为空）就用后台的值，否则用 .env。"""

    def pick(key: str, fallback: str) -> str:
        value = get_setting(db, key)
        return (value if value is not None else fallback or "").strip()

    emails = pick(KEY_EMAILS, settings.FEEDBACK_NOTIFY_EMAILS)
    return {
        "webhook": pick(KEY_WEBHOOK, settings.FEEDBACK_WEBHOOK),
        "secret": pick(KEY_SECRET, settings.FEEDBACK_WEBHOOK_SECRET),
        "emails": [e.strip() for e in emails.replace("；", ",").replace(";", ",").split(",") if e.strip()],
        "public_url": pick(KEY_PUBLIC_URL, settings.APP_PUBLIC_URL).rstrip("/"),
    }


def detect_kind(url: str) -> str:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host.endswith("qyapi.weixin.qq.com"):
        return "wecom"
    if host.endswith("feishu.cn") or host.endswith("larksuite.com"):
        return "feishu"
    if host.endswith("dingtalk.com"):
        return "dingtalk"
    return "generic"


KIND_LABELS = {"wecom": "企业微信", "feishu": "飞书", "dingtalk": "钉钉", "generic": "通用 JSON"}


# ---------------------------------------------------------------- 发送
def _sign_feishu(secret: str, timestamp: int) -> str:
    # 飞书：以 "timestamp\nsecret" 为密钥对空串做 HmacSHA256
    digest = hmac.new(f"{timestamp}\n{secret}".encode("utf-8"), b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _sign_dingtalk(secret: str, timestamp_ms: int) -> str:
    # 钉钉：以 secret 为密钥对 "timestamp\nsecret" 做 HmacSHA256，再 Base64 + URL 编码
    digest = hmac.new(secret.encode("utf-8"), f"{timestamp_ms}\n{secret}".encode("utf-8"), hashlib.sha256).digest()
    return urllib.parse.quote_plus(base64.b64encode(digest).decode())


def build_request(url: str, secret: str, title: str, text: str) -> tuple[str, dict]:
    """按机器人类型构造（最终地址, JSON 请求体）。"""
    kind = detect_kind(url)
    content = f"{title}\n{text}"
    if kind == "wecom":
        return url, {"msgtype": "text", "text": {"content": content}}
    if kind == "feishu":
        payload = {"msg_type": "text", "content": {"text": content}}
        if secret:
            timestamp = int(time.time())
            payload.update(timestamp=str(timestamp), sign=_sign_feishu(secret, timestamp))
        return url, payload
    if kind == "dingtalk":
        if secret:
            timestamp_ms = int(time.time() * 1000)
            joiner = "&" if "?" in url else "?"
            url = f"{url}{joiner}timestamp={timestamp_ms}&sign={_sign_dingtalk(secret, timestamp_ms)}"
        return url, {"msgtype": "text", "text": {"content": content}}
    return url, {"title": title, "text": text}


def post_webhook(url: str, secret: str, title: str, text: str) -> None:
    """发送到机器人；失败抛 RuntimeError（带原因）。"""
    if not url.lower().startswith(("https://", "http://")):
        raise RuntimeError("机器人地址必须以 http:// 或 https:// 开头")
    final_url, payload = build_request(url, secret, title, text)
    request = urllib.request.Request(
        final_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read(4096).decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - 网络错误统一转成可读原因
        raise RuntimeError(f"无法连接机器人地址：{exc}") from exc
    # 三家机器人请求成功但内容有误时都返回 200 + 错误码
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        return
    code = data.get("errcode", data.get("code", data.get("StatusCode", 0)))
    if code not in (0, None, "0"):
        raise RuntimeError(f"机器人返回错误：{data.get('errmsg') or data.get('msg') or code}")


def send(db: Session, title: str, text: str, raise_errors: bool = False) -> dict:
    """按当前配置发送到机器人与邮箱，返回各渠道结果 {"webhook": "ok"/错误/None, "email": ...}。"""
    config = load_config(db)
    result = {"webhook": None, "email": None}
    if config["webhook"]:
        try:
            post_webhook(config["webhook"], config["secret"], title, text)
            result["webhook"] = "ok"
        except RuntimeError as exc:
            logger.warning("反馈通知（机器人）发送失败：%s", exc)
            result["webhook"] = str(exc)
    if config["emails"]:
        try:
            mail.send_mail(config["emails"], title, text)
            result["email"] = "ok"
        except mail.MailError as exc:
            logger.warning("反馈通知（邮件）发送失败：%s", exc)
            result["email"] = str(exc)
    if raise_errors and not any(v == "ok" for v in result.values()) and any(result.values()):
        raise RuntimeError("；".join(v for v in result.values() if v and v != "ok"))
    return result


def feedback_message(db: Session, item: Feedback, user: Optional[User]) -> tuple[str, str]:
    config = load_config(db)
    summary = " ".join((item.content or "").split())
    summary = summary[:120] + ("…" if len(summary) > 120 else "")
    who = f"#{user.id} {user.full_name or user.username} <{user.email}>" if user else "（账号已注销）"
    images = len(json.loads(item.images or "[]"))
    lines = [
        f"类型：{CATEGORY_LABELS.get(item.category, item.category)}",
        f"用户：{who}{'（演示账号）' if user is not None and user.is_demo else ''}",
        f"页面：{item.page or '未知'}",
        f"内容：{summary}",
    ]
    if images:
        lines.append(f"截图：{images} 张")
    if item.contact:
        lines.append(f"联系方式：{item.contact}")
    link = f"{config['public_url']}/admin?tab=feedback&id={item.id}" if config["public_url"] else f"管理后台 → 反馈 #{item.id}"
    lines.append(f"后台：{link}")
    return f"【学业管家】新反馈 #{item.id}", "\n".join(lines)


def notify_new_feedback(feedback_id: int) -> None:
    """BackgroundTasks 调用：自己开数据库会话，任何异常都只记日志。"""
    db = SessionLocal()
    try:
        item = db.get(Feedback, feedback_id)
        if item is None:
            return
        config = load_config(db)
        if not config["webhook"] and not config["emails"]:
            return
        user = db.get(User, item.user_id) if item.user_id else None
        title, text = feedback_message(db, item, user)
        send(db, title, text)
    except Exception:  # noqa: BLE001
        logger.exception("反馈通知发送异常")
    finally:
        db.close()


def mail_reply_to_user(email: str, title: str, text: str) -> None:
    """BackgroundTasks 调用：把管理员回复发到用户邮箱。"""
    try:
        mail.send_mail(email, title, text)
    except Exception:  # noqa: BLE001
        logger.exception("回复邮件发送失败")
