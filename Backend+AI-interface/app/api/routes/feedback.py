# -*- coding: utf-8 -*-
"""
问题反馈：写入数据库（feedbacks 表，管理后台处理与回复），同时保留一份 txt 到服务器的 feedback/ 目录。

txt 文件名：20261024-153012_u12_bug_a1b2c3.txt（时间_用户_类型_随机串，不含用户输入，避免路径注入）。
截图：先 POST /feedback/images 上传（校验真实类型、重新编码去掉 EXIF），再在提交时引用返回的文件名。
新反馈会在后台推送到群机器人 / 管理员邮箱（见 app/services/notify.py）。
"""

import io
import json
import re
import secrets
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from PIL import Image, ImageOps, UnidentifiedImageError

from app.api.deps import DB, CurrentUser
from app.core import ratelimit, timeutil
from app.core.config import settings
from app.core.errors import ApiError, ok
from app.core.security import is_admin_user
from app.models import Feedback, User
from app.schemas import FeedbackIn
from app.services import notify

router = APIRouter(prefix="/feedback", tags=["问题反馈"])

CATEGORY_LABELS = notify.CATEGORY_LABELS
STATUS_LABELS = {"open": "待处理", "processing": "处理中", "resolved": "已解决", "closed": "已关闭"}
DAILY_LIMIT = 10
NAME_RE = re.compile(r"^\d{8}-\d{6}_u\d+_[a-z]+_[0-9a-f]{6}\.txt$")

# 截图：单张 ≤ 3MB，最长边缩到 1600，文件名 f<用户id>_<随机串>.<扩展名>，由服务器生成
IMAGE_MAX_BYTES = 3 * 1024 * 1024
IMAGE_MAX_SIDE = 1600
IMAGE_MAX_PIXELS = 40_000_000
IMAGE_DAILY_LIMIT = 30
IMAGE_RE = re.compile(r"^f(\d+)_[0-9a-f]{20}\.(jpg|png)$")


def _clean(text: Optional[str]) -> str:
    """去掉控制字符，保留换行与制表符。"""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text or "").strip()


def _require_admin(user) -> None:
    if not is_admin_user(user):
        raise ApiError(403, "只有管理员可以查看反馈")


def image_dir():
    return settings.FEEDBACK_DIR / "images"


def feedback_images(item: Feedback) -> list:
    try:
        names = json.loads(item.images or "[]")
    except ValueError:
        return []
    return [name for name in names if isinstance(name, str) and IMAGE_RE.match(name)]


def feedback_to_dict(item: Feedback, user: Optional[User] = None, admin: bool = False) -> dict:
    data = {
        "id": item.id,
        "category": item.category,
        "category_label": CATEGORY_LABELS.get(item.category, item.category),
        "content": item.content,
        "page": item.page or "",
        "images": feedback_images(item),
        "status": item.status or "open",
        "status_label": STATUS_LABELS.get(item.status or "open", item.status),
        "reply": item.reply or "",
        "replied_at": item.replied_at.isoformat() if item.replied_at else None,
        "unread": bool(item.user_unread),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }
    if admin:
        data.update(
            contact=item.contact or "",
            client=item.client or "",
            txt_name=item.txt_name or "",
            replied_by=item.replied_by,
            user=(
                {"id": user.id, "email": user.email, "name": user.full_name or user.username, "avatar": user.avatar or "🦉",
                 "is_demo": bool(user.is_demo), "is_active": bool(user.is_active)}
                if user is not None else None
            ),
        )
    return data


# ---------------------------------------------------------------- 截图
def _sniff(content: bytes) -> Optional[str]:
    """按文件头识别真实类型，不信任文件名与 Content-Type。"""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    return None


def process_image(content: bytes) -> tuple[bytes, str]:
    """校验并重新编码图片：去掉 EXIF 等元数据，按拍摄方向摆正，最长边限制 1600。返回（字节, 扩展名）。"""
    if not content:
        raise ApiError(400, "图片为空")
    if len(content) > IMAGE_MAX_BYTES:
        raise ApiError(413, "单张截图不能超过 3MB")
    kind = _sniff(content)
    if kind is None:
        raise ApiError(400, "只支持 png / jpg / webp 格式的图片")
    try:
        with Image.open(io.BytesIO(content)) as probe:
            if (probe.format or "").lower() != kind or probe.width * probe.height > IMAGE_MAX_PIXELS:
                raise ApiError(400, "图片无法识别或尺寸过大")
            probe.verify()
        image = Image.open(io.BytesIO(content))
        image.load()
        image = ImageOps.exif_transpose(image)
    except ApiError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
        raise ApiError(400, "图片已损坏或格式不正确")

    image.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE))
    has_alpha = image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info)
    out = io.BytesIO()
    if has_alpha:
        # 带透明通道的截图保存为 PNG；新建图像只复制像素，不带任何元数据
        clean = Image.new("RGBA", image.size)
        clean.paste(image.convert("RGBA"))
        clean.save(out, format="PNG", optimize=True)
        return out.getvalue(), "png"
    clean = Image.new("RGB", image.size)
    clean.paste(image.convert("RGB"))
    clean.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue(), "jpg"


@router.post("/images", summary="上传反馈截图（png/jpg/webp，单张 ≤ 3MB），返回文件名供提交反馈时引用")
def upload_image(user: CurrentUser, file: UploadFile = File(...)):
    # 同步函数：图片解码与重新编码在线程池里执行，不阻塞事件循环
    if not ratelimit.hit("feedback-image", str(user.id), IMAGE_DAILY_LIMIT, 86400):
        raise ApiError(429, "今天上传的截图太多了，明天再来吧")
    content = file.file.read(IMAGE_MAX_BYTES + 1)
    data, ext = process_image(content)
    folder = image_dir()
    folder.mkdir(parents=True, exist_ok=True)
    name = f"f{user.id}_{secrets.token_hex(10)}.{ext}"
    (folder / name).write_bytes(data)
    return ok({"name": name, "size": len(data)}, "截图已上传")


@router.get("/images/{name}", summary="查看反馈截图（本人或管理员）")
def get_image(name: str, user: CurrentUser):
    match = IMAGE_RE.match(name)
    path = image_dir() / name
    if not match or not path.is_file():
        raise ApiError(404, "图片不存在")
    if int(match.group(1)) != user.id and not is_admin_user(user):
        raise ApiError(403, "没有权限查看这张图片")
    media = "image/png" if name.endswith(".png") else "image/jpeg"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "private, max-age=86400"})


# ---------------------------------------------------------------- 提交与我的反馈
@router.post("", summary="提交问题反馈（入库，同时保存为服务器上的 txt 文件，并通知管理员）")
def submit_feedback(payload: FeedbackIn, request: Request, user: CurrentUser, db: DB, background: BackgroundTasks):
    now = timeutil.now()
    day_start = now.replace(hour=0, minute=0, second=0)
    mine_today = db.query(Feedback.id).filter(Feedback.user_id == user.id, Feedback.created_at >= day_start).count()
    if mine_today >= DAILY_LIMIT:
        raise ApiError(429, f"今天已经提交了 {DAILY_LIMIT} 条反馈，明天再来吧")

    images = []
    for name in payload.images:
        match = IMAGE_RE.match(name or "")
        if not match or int(match.group(1)) != user.id or not (image_dir() / name).is_file():
            raise ApiError(400, "截图无效，请重新上传")
        if name not in images:
            images.append(name)

    client = _clean(payload.client) or request.headers.get("user-agent", "")[:300]
    folder = settings.FEEDBACK_DIR
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{now.strftime('%Y%m%d-%H%M%S')}_u{user.id}_{payload.category}_{secrets.token_hex(3)}.txt"
    lines = [
        f"时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"类型：{CATEGORY_LABELS[payload.category]}",
        f"用户：#{user.id} {user.full_name or user.username} <{user.email}>{'（演示账号）' if user.is_demo else ''}",
        f"联系方式：{_clean(payload.contact) or '未填写'}",
        f"所在页面：{_clean(payload.page) or '未知'}",
        f"客户端：{client}",
        f"版本：{settings.APP_VERSION}",
    ]
    if images:
        lines.append(f"截图：{', '.join('images/' + n for n in images)}")
    lines += ["-" * 40, _clean(payload.content), ""]
    (folder / name).write_text("\n".join(lines), encoding="utf-8")

    item = Feedback(
        user_id=user.id,
        category=payload.category,
        content=_clean(payload.content),
        contact=_clean(payload.contact) or None,
        page=_clean(payload.page) or None,
        client=client[:300],
        images=json.dumps(images),
        status="open",
        txt_name=name,
        created_at=now,
    )
    db.add(item)
    db.commit()
    background.add_task(notify.notify_new_feedback, item.id)
    return ok({"id": item.id, "txt_id": name.removesuffix(".txt"), "images": images}, "感谢反馈！我们会尽快处理")


@router.get("/mine", summary="我的反馈：处理状态与管理员回复")
def my_feedback(user: CurrentUser, db: DB, limit: int = 50):
    items = (
        db.query(Feedback).filter(Feedback.user_id == user.id)
        .order_by(Feedback.id.desc()).limit(max(1, min(limit, 100))).all()
    )
    unread = sum(1 for item in items if item.user_unread)
    return ok({"items": [feedback_to_dict(item) for item in items], "unread": unread})


@router.post("/{feedback_id}/read", summary="把某条反馈的回复标记为已读")
def mark_read(feedback_id: int, user: CurrentUser, db: DB):
    item = db.get(Feedback, feedback_id)
    if item is None or item.user_id != user.id:
        raise ApiError(404, "反馈不存在")
    if item.user_unread:
        item.user_unread = False
        db.commit()
    return ok(feedback_to_dict(item))


# ---------------------------------------------------------------- 兼容旧接口（管理员）
@router.get("", summary="（管理员）最近的反馈列表")
def list_feedback(user: CurrentUser, db: DB, days: int = 30):
    _require_admin(user)
    since = timeutil.now() - timedelta(days=max(1, min(days, 365)))
    rows = db.query(Feedback).filter(Feedback.created_at >= since).order_by(Feedback.id.desc()).limit(200).all()
    total = db.query(Feedback.id).filter(Feedback.created_at >= since).count()
    items = [
        {"id": item.id, "txt_id": (item.txt_name or "").removesuffix(".txt"), "category": item.category,
         "status": item.status, "preview": (item.content or "")[:120],
         "created_at": item.created_at.isoformat() if item.created_at else None}
        for item in rows
    ]
    return ok({"items": items, "total": total, "folder": str(settings.FEEDBACK_DIR)})


@router.get("/{feedback_id}", summary="（管理员）下载某条反馈的 txt 原文（数字编号或 txt 文件名均可）", response_class=PlainTextResponse)
def get_feedback(feedback_id: str, user: CurrentUser, db: DB):
    _require_admin(user)
    name = f"{feedback_id}.txt"
    if feedback_id.isdigit():
        item = db.get(Feedback, int(feedback_id))
        name = item.txt_name if item is not None and item.txt_name else ""
    path = settings.FEEDBACK_DIR / name
    if not NAME_RE.match(name) or not path.is_file():
        raise ApiError(404, "反馈不存在")
    return PlainTextResponse(path.read_text(encoding="utf-8", errors="replace"))
