# -*- coding: utf-8 -*-
"""
AI 扩展：每周 AI 复盘、PDF 讲义提取章节。（联网搜索只给智能体用，见 app/ai/search.py，没有对外接口）

  GET  /ai/review/weekly      某一周的学习统计 + AI 复盘与下周建议（结果缓存，refresh=1 重新生成）
  POST /ai/materials/outline  上传 PDF 讲义，提取章节树并估算复习时长
"""

from typing import Optional

from fastapi import APIRouter, File, Query, UploadFile

from app.api.deps import DB, CurrentUser
from app.core.config import settings
from app.core.errors import ApiError, ok
from app.schemas import DATE_PATTERN
from app.services import materials, weekly_review

# 不设 prefix：本模块内的路径写完整（如 /ai/review/weekly），由 main.py 统一注册
router = APIRouter(tags=["AI 扩展"])


@router.get("/ai/review/weekly", summary="每周 AI 复盘：默认上一完整周（周一开始），refresh=1 重新生成")
def get_weekly_review(
    user: CurrentUser,
    db: DB,
    week_start: Optional[str] = Query(default=None, pattern=DATE_PATTERN, description="该周任意一天，按周一对齐"),
    refresh: int = Query(default=0, ge=0, le=1),
):
    data = weekly_review.weekly_review(db, user, week_start, refresh=bool(refresh))
    message = "复盘已生成" if not data.get("cached") else "已读取本周复盘"
    return ok(data, message)


@router.post("/ai/materials/outline", summary="PDF 讲义提取章节：书签 + 正文标题，按字数估算复习时长")
def materials_outline(user: CurrentUser, db: DB, file: UploadFile = File(..., description="PDF 讲义 / 课件")):
    content = file.file.read(settings.MAX_UPLOAD_BYTES + 1)
    if not content:
        raise ApiError(422, "文件为空")
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise ApiError(413, f"文件不能超过 {settings.MAX_UPLOAD_BYTES // (1024 * 1024)}MB")
    data = materials.extract_outline(db, user, file.filename or "讲义.pdf", content)
    return ok(data, f"提取到 {len(data['chapters'])} 个章节")
