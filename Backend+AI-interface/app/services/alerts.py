# -*- coding: utf-8 -*-
"""
运维告警：后端 5xx / 前端错误短时间激增时，通过反馈通知的机器人与邮箱（app/services/notify.py）告警，带冷却。

- record_server_error()：main.py 的中间件在响应状态 ≥ 500 时调用；
- record_client_error()：POST /client-errors 每记录一次调用；
- 计数存在 rate_events 表（与限流共用，重启不丢）；冷却时间记在 AppSetting（alert_last_<kind>）。
通知在后台线程发送，绝不阻塞或影响请求本身。

命令行（健康检查脚本 deploy/healthcheck.sh 在后端不可用时调用，此时后端进程可能已经挂了）：
  python -m app.services.alerts notify "标题" "内容"
"""

import logging
import sys
import threading
import time
from typing import Callable, Optional

from app.core import ratelimit, timeutil
from app.core.config import settings
from app.core.database import SessionLocal

logger = logging.getLogger("study_planner.alerts")

KINDS = {
    "5xx": {"bucket": "alert-5xx", "label": "后端 5xx 错误"},
    "client": {"bucket": "alert-client", "label": "前端运行时错误"},
}


def _threshold(kind: str) -> int:
    return settings.ALERT_5XX if kind == "5xx" else settings.ALERT_CLIENT_ERRORS


def _spawn(target: Callable, *args) -> None:
    """后台执行（测试里替换成同步调用）。"""
    threading.Thread(target=target, args=args, daemon=True).start()


def _cooldown_key(kind: str) -> str:
    return f"alert_last_{kind}"


def _claim_cooldown(kind: str) -> bool:
    """冷却期外则记下本次告警时间并返回 True（同一类告警 COOLDOWN 分钟内只发一次）。"""
    from app.models import AppSetting

    db = SessionLocal()
    try:
        row = db.get(AppSetting, _cooldown_key(kind))
        now = time.time()
        try:
            last = float(row.value) if row is not None and row.value else 0.0
        except ValueError:
            last = 0.0
        if now - last < settings.ALERT_COOLDOWN_MINUTES * 60:
            return False
        if row is None:
            db.add(AppSetting(key=_cooldown_key(kind), value=str(now)))
        else:
            row.value = str(now)
        db.commit()
        return True
    finally:
        db.close()


def send(title: str, text: str) -> dict:
    """按反馈通知的配置发送（机器人 + 邮件）；返回各渠道结果。数据库读不了时改用 .env 里的配置。"""
    from sqlalchemy.exc import SQLAlchemyError

    from app.services import mail, notify

    db = SessionLocal()
    try:
        return notify.send(db, title, text)
    except SQLAlchemyError:
        logger.warning("读取通知配置失败（数据库不可用），改用 .env 中的 FEEDBACK_WEBHOOK / FEEDBACK_NOTIFY_EMAILS")
    finally:
        db.close()
    result = {"webhook": None, "email": None}
    if settings.FEEDBACK_WEBHOOK:
        try:
            notify.post_webhook(settings.FEEDBACK_WEBHOOK, settings.FEEDBACK_WEBHOOK_SECRET, title, text)
            result["webhook"] = "ok"
        except RuntimeError as exc:
            result["webhook"] = str(exc)
    emails = [e.strip() for e in (settings.FEEDBACK_NOTIFY_EMAILS or "").split(",") if e.strip()]
    if emails:
        try:
            mail.send_mail(emails, title, text)
            result["email"] = "ok"
        except mail.MailError as exc:
            result["email"] = str(exc)
    return result


def _check(kind: str, sample: str = "") -> Optional[dict]:
    """窗口内次数达到阈值且不在冷却期时发告警；返回发送结果（测试用），否则 None。"""
    threshold = _threshold(kind)
    if threshold <= 0:
        return None
    window = max(1, settings.ALERT_WINDOW_MINUTES)
    bucket = KINDS[kind]["bucket"]
    total = ratelimit.count(bucket, "", window * 60)
    if total < threshold or not _claim_cooldown(kind):
        return None
    lines = [
        f"最近 {window} 分钟内出现 {total} 次{KINDS[kind]['label']}（阈值 {threshold}）。",
        f"时间：{timeutil.now():%Y-%m-%d %H:%M:%S}",
    ]
    if sample:
        lines.append(f"最近一次：{sample[:200]}")
    lines.append("请查看服务器日志（journalctl -u xueyeguanjia -n 200）" if kind == "5xx" else "请到管理后台 →「错误」查看")
    lines.append(f"{settings.ALERT_COOLDOWN_MINUTES} 分钟内不再重复提醒。")
    return send(f"【学业管家】告警：{KINDS[kind]['label']}激增", "\n".join(lines))


def _record(kind: str, sample: str) -> None:
    try:
        ratelimit.add(KINDS[kind]["bucket"], "")
        _check(kind, sample)
    except Exception:  # noqa: BLE001 - 告警出错只记日志
        logger.exception("错误告警处理失败")


def record_server_error(method: str, path: str, status: int) -> None:
    _spawn(_record, "5xx", f"{status} {method} {path}")


def record_client_error(message: str, page: str = "") -> None:
    _spawn(_record, "client", f"{message} @ {page}" if page else message)


class ErrorAlertMiddleware:
    """
    纯 ASGI 中间件：响应状态 ≥ 500 或抛出未处理异常时计数（不缓冲响应体，SSE 流式不受影响）。
    未处理异常会继续向外抛，由全局处理器返回统一的 500 信封。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        reported = False

        def report(status: int) -> None:
            nonlocal reported
            if not reported:
                reported = True
                record_server_error(scope.get("method", ""), scope.get("path", ""), status)

        async def wrapped(message):
            if message.get("type") == "http.response.start" and int(message.get("status", 200)) >= 500:
                report(int(message["status"]))
            await send(message)

        try:
            await self.app(scope, receive, wrapped)
        except Exception:
            report(500)
            raise


# ---------------------------------------------------------------- 命令行
def main(argv) -> int:
    if len(argv) >= 2 and argv[0] == "notify":
        title, text = argv[1], argv[2] if len(argv) > 2 else ""
        try:
            result = send(title, text)
        except Exception as exc:  # noqa: BLE001 - 数据库不可读时也要给出结果
            print(f"发送失败：{exc}", file=sys.stderr)
            return 2
        print(result)
        return 0 if any(v == "ok" for v in result.values()) or not any(result.values()) else 1
    print('用法：python -m app.services.alerts notify "标题" "内容"', file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
