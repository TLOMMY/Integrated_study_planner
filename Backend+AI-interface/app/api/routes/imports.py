# -*- coding: utf-8 -*-
"""
课表导入：先预览，确认后再写库。

  POST /import/timetable          Excel / CSV 文件（mode=preview|commit，selected 指定导入哪几门）
  POST /import/timetable/web      教务系统网页（.html/.mhtml/粘贴的源代码或 JSON），参数同上
  POST /import/timetable/ai       图片 / PDF 交给大模型识别，只返回预览
  POST /import/timetable/commit   提交（可能经用户勾选过的）预览课程，AI 识别结果走这里，不会再次调用模型
"""

from typing import Callable, List, Literal, Optional

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.ai import providers
from app.ai.llm import ModelConfig
from app.api.deps import DB, CurrentUser
from app.core.config import settings
from app.core.errors import ApiError, ok
from app.schemas import DATE_PATTERN
from app.services import import_common, schedule
from app.services.import_web import parse_web_timetable
from app.services.importer import parse_timetable

router = APIRouter(prefix="/import", tags=["导入"])


def _read_upload(file: UploadFile) -> bytes:
    content = file.file.read(settings.MAX_UPLOAD_BYTES + 1)
    if not content:
        raise ApiError(422, "文件为空")
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise ApiError(413, f"文件不能超过 {settings.MAX_UPLOAD_BYTES // (1024 * 1024)}MB")
    return content


def _file_import(parser: Callable, user, db, file: UploadFile, mode: str, replace: bool, selected: Optional[str]):
    """Excel 与网页导入共用：解析 → 预览；commit 时按 selected 过滤后写库。"""
    content = _read_upload(file)
    result = parser(file.filename or "", content, user)
    data = import_common.build_preview(
        db, user, file_name=file.filename, fmt=result.format, courses=result.courses, skipped=result.skipped,
        semester=result.semester, semester_start=result.semester_start, total_weeks=result.total_weeks,
    )
    if mode == "preview":
        return ok(data, f"解析到 {data['success_count']} 门课程")

    chosen = import_common.select_indexes(data["courses"], selected)
    data["courses"], data["success_count"] = chosen, len(chosen)
    data["reward"] = import_common.commit_courses(
        db, user, semester=data["semester"], courses=chosen, replace=replace,
        semester_start=result.semester_start, total_weeks=result.total_weeks,
        file_name=file.filename, fail_count=len(result.skipped),
    )
    return ok(data, f"已导入 {len(chosen)} 门课程")


@router.post("/timetable", summary="导入课表文件：mode=preview 只解析，mode=commit 写入（selected 指定导入哪几门）")
def import_timetable(
    user: CurrentUser,
    db: DB,
    file: UploadFile = File(...),
    mode: Literal["preview", "commit"] = "preview",
    replace: bool = True,
    selected: Optional[str] = Form(default=None, description="逗号分隔的预览序号；不传则全部导入"),
):
    return _file_import(parse_timetable, user, db, file, mode, replace, selected)


@router.post("/timetable/web", summary="从教务系统网页导入：上传保存的 .html/.mhtml，或把粘贴的源代码/JSON 作为文件上传")
def import_timetable_web(
    user: CurrentUser,
    db: DB,
    file: UploadFile = File(..., description="网页文件；粘贴的文字由前端包装成 pasted.html / pasted.json"),
    mode: Literal["preview", "commit"] = "preview",
    replace: bool = True,
    selected: Optional[str] = Form(default=None, description="逗号分隔的预览序号；不传则全部导入"),
):
    return _file_import(parse_web_timetable, user, db, file, mode, replace, selected)


# ---------------------------------------------------------------- AI 识别
def _ai_config(db, user, provider_id: Optional[str]) -> ModelConfig:
    choice = (provider_id or "").strip()
    if choice in ("", "auto", "active"):
        config = providers.resolve(db, user)
        if config is None:
            raise ApiError(422, "当前使用的是本地规则引擎，无法识别图片：请在 AI 设置中添加并选择一个大模型")
        return config
    if choice == "env":
        config = providers.env_config()
        if config is None:
            raise ApiError(422, "服务器没有配置 DeepSeek，请选择你自己添加的模型")
        return config
    if choice.isdigit():
        provider = providers.get_owned(db, user, int(choice))
        if provider is None:
            raise ApiError(404, "模型配置不存在或已被删除")
        return providers.to_config(provider)
    raise ApiError(422, "模型参数不合法")


@router.post("/timetable/ai", summary="AI 识别课表图片 / PDF：只返回预览，确认后调用 /import/timetable/commit")
def import_timetable_ai(
    user: CurrentUser,
    db: DB,
    file: UploadFile = File(..., description="png / jpg / webp 截图或照片，或 PDF"),
    provider_id: Optional[str] = Form(default=None, description="模型配置 id、env（服务器 DeepSeek）；不传则用当前启用的模型"),
):
    from app.ai import vision

    content = _read_upload(file)
    config = _ai_config(db, user, provider_id)
    data = vision.recognize_timetable(db, user, config, file.filename or "", content)
    return ok(data, f"识别到 {data['success_count']} 门课程，请核对后导入")


class ImportCourseIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    course_name: str = Field(min_length=1, max_length=160)
    teacher: Optional[str] = Field(default="", max_length=120)
    classroom: Optional[str] = Field(default="", max_length=80)
    day_of_week: int = Field(ge=1, le=7)
    start_period: int = Field(ge=1, le=16)
    end_period: int = Field(ge=1, le=16)
    weeks: Optional[List[int]] = Field(default=None, max_length=30)
    week_text: Optional[str] = Field(default=None, max_length=80)


class ImportCommitIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    courses: List[ImportCourseIn] = Field(max_length=300)
    semester: Optional[str] = Field(default=None, min_length=1, max_length=40)
    semester_start: Optional[str] = Field(default=None, pattern=DATE_PATTERN)
    total_weeks: Optional[int] = Field(default=None, ge=1, le=30)
    replace: bool = True
    file_name: Optional[str] = Field(default=None, max_length=200)
    fail_count: int = Field(default=0, ge=0, le=1000)


@router.post("/timetable/commit", summary="提交预览中的课程（AI 识别结果），服务器重新校验后写入")
def commit_timetable(payload: ImportCommitIn, user: CurrentUser, db: DB):
    if not payload.courses:
        raise ApiError(422, "请至少勾选一门课程")
    total = payload.total_weeks or int(user.total_weeks or 20)
    courses = []
    for index, raw in enumerate(payload.courses, start=1):
        course, reason = import_common.normalize_course(raw.model_dump(), user, total)
        if course is None:
            raise ApiError(422, f"第 {index} 门「{raw.course_name}」{reason}")
        courses.append(course)
    preview = import_common.with_times(user, courses)
    semester = payload.semester or schedule.effective_semester(db, user)
    reward = import_common.commit_courses(
        db, user, semester=semester, courses=preview, replace=payload.replace,
        semester_start=payload.semester_start, total_weeks=payload.total_weeks,
        file_name=payload.file_name, fail_count=payload.fail_count,
    )
    return ok({"semester": semester, "courses": preview, "success_count": len(preview), "reward": reward},
              f"已导入 {len(preview)} 门课程")
