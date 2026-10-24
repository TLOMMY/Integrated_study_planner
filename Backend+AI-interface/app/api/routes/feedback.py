# -*- coding: utf-8 -*-
"""
问题反馈：每条反馈保存为一个 txt 文件，技术人员直接到服务器的 feedback/ 目录查看即可。

文件名：20261024-153012_u12_bug_a1b2c3.txt（时间_用户_类型_随机串，不含用户输入，避免路径注入）。
.env 里配置 ADMIN_EMAILS 后，这些账号可以通过 GET /feedback 在线查看与下载。
"""

import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app.api.deps import DB, CurrentUser
from app.core import timeutil
from app.core.config import settings
from app.core.errors import ApiError, ok
from app.schemas import FeedbackIn

router = APIRouter(prefix="/feedback", tags=["问题反馈"])

CATEGORY_LABELS = {"bug": "功能异常", "suggestion": "功能建议", "ui": "界面问题", "other": "其他"}
DAILY_LIMIT = 10
NAME_RE = re.compile(r"^\d{8}-\d{6}_u\d+_[a-z]+_[0-9a-f]{6}\.txt$")


def _clean(text: str) -> str:
    """去掉控制字符，保留换行与制表符。"""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text or "").strip()


def _require_admin(user) -> None:
    if (user.email or "").lower() not in settings.ADMIN_EMAILS:
        raise ApiError(403, "只有管理员可以查看反馈")


@router.post("", summary="提交问题反馈（保存为服务器上的 txt 文件）")
def submit_feedback(payload: FeedbackIn, request: Request, user: CurrentUser):
    folder = settings.FEEDBACK_DIR
    folder.mkdir(parents=True, exist_ok=True)
    now = timeutil.now()
    today_prefix = now.strftime("%Y%m%d")
    mine_today = list(folder.glob(f"{today_prefix}-*_u{user.id}_*.txt"))
    if len(mine_today) >= DAILY_LIMIT:
        raise ApiError(429, f"今天已经提交了 {DAILY_LIMIT} 条反馈，明天再来吧")

    name = f"{now.strftime('%Y%m%d-%H%M%S')}_u{user.id}_{payload.category}_{secrets.token_hex(3)}.txt"
    lines = [
        f"时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"类型：{CATEGORY_LABELS[payload.category]}",
        f"用户：#{user.id} {user.full_name or user.username} <{user.email}>{'（演示账号）' if user.is_demo else ''}",
        f"联系方式：{_clean(payload.contact) or '未填写'}",
        f"所在页面：{_clean(payload.page) or '未知'}",
        f"客户端：{_clean(payload.client) or request.headers.get('user-agent', '')[:300]}",
        f"版本：{settings.APP_VERSION}",
        "-" * 40,
        _clean(payload.content),
        "",
    ]
    (folder / name).write_text("\n".join(lines), encoding="utf-8")
    return ok({"id": name.removesuffix(".txt")}, "感谢反馈！我们会尽快处理")


@router.get("", summary="（管理员）最近的反馈列表")
def list_feedback(user: CurrentUser, days: int = 30):
    _require_admin(user)
    folder = settings.FEEDBACK_DIR
    if not folder.exists():
        return ok({"items": [], "total": 0, "folder": str(folder)})
    since = (timeutil.now() - timedelta(days=max(1, min(days, 365)))).strftime("%Y%m%d")
    items = []
    for path in sorted(folder.glob("*.txt"), reverse=True):
        if not NAME_RE.match(path.name) or path.name[:8] < since:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        items.append({"id": path.stem, "category": path.stem.split("_")[2], "preview": text.split("-" * 40)[-1].strip()[:120],
                      "created_at": path.name[:15]})
    return ok({"items": items[:200], "total": len(items), "folder": str(folder)})


@router.get("/{feedback_id}", summary="（管理员）下载某条反馈的 txt 原文", response_class=PlainTextResponse)
def get_feedback(feedback_id: str, user: CurrentUser):
    _require_admin(user)
    name = f"{feedback_id}.txt"
    path = settings.FEEDBACK_DIR / name
    if not NAME_RE.match(name) or not path.is_file():
        raise ApiError(404, "反馈不存在")
    return PlainTextResponse(path.read_text(encoding="utf-8", errors="replace"))
