# -*- coding: utf-8 -*-
"""
统一响应信封与全局异常处理。

所有接口（包括报错）都返回 {"code": int, "message": str, "data": any}，
code 与 HTTP 状态码一致，前端只需判断一处。
"""

import logging
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("study_planner")


class ApiError(Exception):
    """业务异常：抛出后由全局处理器转换为统一信封。"""

    def __init__(self, status_code: int, message: str, data: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.data = data


def ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 200, "message": message, "data": data}


def _envelope(status_code: int, message: str, data: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({"code": status_code, "message": message, "data": data}),
    )


_HTTP_MESSAGES = {
    400: "请求参数有误",
    401: "请先登录",
    403: "没有权限执行此操作",
    404: "接口不存在",
    405: "请求方法不被允许",
    413: "上传文件过大",
    429: "请求过于频繁",
}

_FIELD_LABELS = {
    "title": "标题",
    "password": "密码",
    "new_password": "新密码",
    "old_password": "原密码",
    "email": "邮箱",
    "username": "用户名",
    "identifier": "账号",
    "full_name": "昵称",
    "course_name": "课程名称",
    "day_of_week": "星期",
    "start_period": "开始节次",
    "end_period": "结束节次",
    "weeks": "上课周次",
    "due_date": "日期",
    "start_time": "开始时间",
    "duration_minutes": "时长",
    "priority": "优先级",
    "repeat_rule": "重复规则",
    "message": "需求描述",
    "daily_goal_minutes": "每日目标",
    "semester_start": "开学日期",
    "total_weeks": "学期周数",
    "period_times": "节次时间",
    "start_date": "开始日期",
    "end_date": "结束日期",
    "tasks": "任务列表",
}


def _humanize_validation_error(error: dict) -> str:
    loc = [str(part) for part in error.get("loc", []) if part not in ("body", "query", "path")]
    field = loc[-1] if loc else ""
    label = _FIELD_LABELS.get(field, field)
    error_type = error.get("type", "")
    ctx = error.get("ctx") or {}

    if error_type == "missing":
        return f"缺少必填项：{label}"
    if error_type == "value_error":
        # 自定义校验器的消息已经是完整中文句子
        message = str(ctx.get("error") or error.get("msg", ""))
        if "email" in message.lower():
            return "邮箱格式不正确"
        return message.removeprefix("Value error, ")
    if error_type == "string_too_short":
        return f"{label}至少需要 {ctx.get('min_length')} 个字符"
    if error_type == "string_too_long":
        return f"{label}不能超过 {ctx.get('max_length')} 个字符"
    if error_type == "string_pattern_mismatch":
        return f"{label}格式不正确"
    if error_type in {"greater_than_equal", "greater_than"}:
        return f"{label}不能小于 {ctx.get('ge', ctx.get('gt'))}"
    if error_type in {"less_than_equal", "less_than"}:
        return f"{label}不能大于 {ctx.get('le', ctx.get('lt'))}"
    if error_type in {"int_parsing", "int_type", "float_parsing"}:
        return f"{label}必须是数字"
    if error_type in {"literal_error", "enum"}:
        return f"{label}取值不合法"
    if error_type == "json_invalid":
        return "请求体不是合法的 JSON"
    return f"{label or '参数'}不合法"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError):
        return _envelope(exc.status_code, exc.message, exc.data)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException):
        detail: Optional[str] = exc.detail if isinstance(exc.detail, str) else None
        if exc.status_code in _HTTP_MESSAGES and (not detail or detail.isascii()):
            detail = _HTTP_MESSAGES[exc.status_code]
        return _envelope(exc.status_code, detail or "请求失败")

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError):
        errors = exc.errors()
        details = [
            {
                "field": ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")),
                "message": _humanize_validation_error(err),
            }
            for err in errors
        ]
        message = details[0]["message"] if details else "请求参数有误"
        return _envelope(422, message, {"errors": details})

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception):
        logger.exception("Unhandled error: %s", exc)
        return _envelope(500, "服务器开小差了，请稍后重试")
