# -*- coding: utf-8 -*-
"""
发送邮件。

MAIL_BACKEND：
- smtp：按 SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_SSL / SMTP_FROM 真实发送；
- console：只把邮件内容写进日志（开发环境，验证码在后端控制台里看）；
- memory：记在 OUTBOX 列表里，供测试读取。
留空时：配置了 SMTP_HOST 就用 smtp，否则 console。
"""

import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr
from typing import Iterable, List

from app.core.config import settings

logger = logging.getLogger("study_planner.mail")

# memory 模式下已"发送"的邮件：{"to": [...], "subject": str, "body": str}
OUTBOX: List[dict] = []
_lock = threading.Lock()


class MailError(Exception):
    pass


def backend() -> str:
    name = settings.MAIL_BACKEND
    if name in {"smtp", "console", "memory"}:
        return name
    return "smtp" if settings.SMTP_HOST else "console"


def can_deliver() -> bool:
    """是否能把邮件真正送到用户手里（console 模式只写日志）。"""
    return backend() in {"smtp", "memory"}


def send_mail(to: Iterable[str] | str, subject: str, body: str) -> None:
    """发送纯文本邮件；失败抛 MailError。"""
    recipients = [to] if isinstance(to, str) else [addr for addr in to if addr]
    if not recipients:
        return
    mode = backend()
    if mode == "memory":
        with _lock:
            OUTBOX.append({"to": recipients, "subject": subject, "body": body})
        return
    if mode == "console":
        logger.info("[邮件·未发送，仅记录] 收件人=%s 主题=%s\n%s", ",".join(recipients), subject, body)
        return

    sender = settings.SMTP_FROM or settings.SMTP_USER
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings.APP_NAME, sender))
    message["To"] = ", ".join(recipients)
    message.set_content(body)
    try:
        if settings.SMTP_SSL:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
            server.starttls(context=ssl.create_default_context())
        with server:
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("邮件发送失败：%s", exc)
        raise MailError("邮件发送失败，请稍后重试") from exc


def last_to(address: str) -> dict | None:
    """（测试用）memory 模式下发给某个地址的最后一封邮件。"""
    with _lock:
        for item in reversed(OUTBOX):
            if address.lower() in [a.lower() for a in item["to"]]:
                return item
    return None
