# -*- coding: utf-8 -*-
"""请求体校验模型。响应统一由各 service 的 *_to_dict 构造。"""

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class _Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


# ---------------------------------------------------------------- 认证 / 用户
class RegisterIn(_Base):
    email: EmailStr
    password: str = Field(min_length=6, max_length=64)
    full_name: Optional[str] = Field(default=None, max_length=40)
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)


class LoginIn(_Base):
    identifier: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    password: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _need_identifier(self):
        if not (self.identifier or self.email or self.username):
            raise ValueError("请输入邮箱或用户名")
        return self

    @property
    def account(self) -> str:
        return (self.identifier or self.email or self.username or "").strip()


class UserUpdateIn(_Base):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    avatar: Optional[str] = Field(default=None, min_length=1, max_length=8)
    daily_goal_minutes: Optional[int] = Field(default=None, ge=10, le=600)


class PasswordIn(_Base):
    old_password: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=6, max_length=64)


class EmailChangeIn(_Base):
    email: EmailStr
    password: str = Field(min_length=1, max_length=64)


PHONE_PATTERN = r"^1[3-9]\d{9}$"


class PhoneChangeIn(_Base):
    # 留空表示解绑
    phone: Optional[str] = Field(default=None, max_length=20)
    password: str = Field(min_length=1, max_length=64)

    @field_validator("phone")
    @classmethod
    def _phone(cls, value):
        if value in (None, ""):
            return None
        value = re.sub(r"[\s-]", "", value)
        if value.startswith("+86"):
            value = value[3:]
        if not re.match(PHONE_PATTERN, value):
            raise ValueError("请输入 11 位中国大陆手机号")
        return value


class PasswordConfirmIn(_Base):
    password: str = Field(min_length=1, max_length=64)


SEGMENT = Literal["morning", "afternoon", "evening"]


class StudyPrefsIn(_Base):
    """学习时段偏好：auto 按专注记录自动判断，custom 使用下面的设定。AI 排程会读取。"""

    mode: Literal["auto", "custom"] = "auto"
    segments: List[SEGMENT] = Field(default_factory=list, max_length=3)
    avoid: List[SEGMENT] = Field(default_factory=list, max_length=2)
    earliest: str = Field(default="08:00", pattern=TIME_PATTERN)
    latest: str = Field(default="22:00", pattern=TIME_PATTERN)
    block_minutes: int = Field(default=45, ge=20, le=120)
    rest_minutes: int = Field(default=10, ge=0, le=30)
    daily_minutes: Optional[int] = Field(default=None, ge=30, le=360)

    @model_validator(mode="after")
    def _range(self):
        if self.latest <= self.earliest:
            raise ValueError("最晚时间必须晚于最早时间")
        if set(self.segments) & set(self.avoid):
            raise ValueError("同一个时段不能既偏好又避开")
        return self


class FeedbackIn(_Base):
    category: Literal["bug", "suggestion", "ui", "other"] = "bug"
    content: str = Field(min_length=5, max_length=2000)
    contact: Optional[str] = Field(default=None, max_length=100)
    page: Optional[str] = Field(default=None, max_length=200)
    client: Optional[str] = Field(default=None, max_length=300)


# ---------------------------------------------------------------- 任务
class TaskIn(_Base):
    title: str = Field(min_length=1, max_length=200)
    subject: Optional[str] = Field(default=None, max_length=80)
    note: Optional[str] = Field(default=None, max_length=1000)
    due_date: Optional[str] = Field(default=None, pattern=DATE_PATTERN)
    start_time: Optional[str] = Field(default=None, pattern=TIME_PATTERN)
    duration_minutes: int = Field(default=30, ge=5, le=480)
    priority: int = Field(default=0, ge=0, le=3)
    repeat_rule: Literal["none", "daily", "weekdays", "weekly"] = "none"
    plan_id: Optional[int] = None
    source: Literal["manual", "quick"] = "manual"


class TaskUpdateIn(_Base):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    subject: Optional[str] = Field(default=None, max_length=80)
    note: Optional[str] = Field(default=None, max_length=1000)
    due_date: Optional[str] = Field(default=None, pattern=DATE_PATTERN)
    start_time: Optional[str] = Field(default=None, pattern=TIME_PATTERN)
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=480)
    priority: Optional[int] = Field(default=None, ge=0, le=3)
    repeat_rule: Optional[Literal["none", "daily", "weekdays", "weekly"]] = None
    plan_id: Optional[int] = None


# ---------------------------------------------------------------- 课表
class CourseIn(_Base):
    course_name: str = Field(min_length=1, max_length=160)
    teacher: Optional[str] = Field(default="", max_length=120)
    classroom: Optional[str] = Field(default="", max_length=80)
    day_of_week: int = Field(ge=1, le=7)
    start_period: int = Field(ge=1, le=16)
    end_period: int = Field(ge=1, le=16)
    weeks: Optional[List[int]] = None
    week_text: Optional[str] = Field(default=None, max_length=80)
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    note: Optional[str] = Field(default="", max_length=200)
    force: bool = False

    @model_validator(mode="after")
    def _check(self):
        if self.end_period < self.start_period:
            raise ValueError("结束节次不能早于开始节次")
        if self.weeks is not None:
            self.weeks = sorted({int(w) for w in self.weeks})
            if not self.weeks:
                raise ValueError("请至少选择一个上课周")
        return self


class PeriodTime(_Base):
    start: str = Field(pattern=TIME_PATTERN)
    end: str = Field(pattern=TIME_PATTERN)


class TimetableSettingsIn(_Base):
    semester: Optional[str] = Field(default=None, min_length=1, max_length=40)
    semester_start: Optional[str] = Field(default=None, pattern=DATE_PATTERN)
    total_weeks: Optional[int] = Field(default=None, ge=1, le=30)
    period_times: Optional[List[PeriodTime]] = None

    @field_validator("period_times")
    @classmethod
    def _ordered(cls, value):
        if value is None:
            return value
        if not 4 <= len(value) <= 16:
            raise ValueError("节次数量需在 4-16 之间")
        previous = "00:00"
        for index, item in enumerate(value, start=1):
            if not (previous <= item.start < item.end):
                raise ValueError(f"第 {index} 节的时间需晚于上一节且开始早于结束")
            previous = item.end
        return value


# ---------------------------------------------------------------- 专注 / 计划 / AI
class FocusIn(_Base):
    task_id: Optional[int] = None
    duration_minutes: int = Field(ge=1, le=300)
    planned_minutes: Optional[int] = Field(default=None, ge=1, le=300)
    completed: bool = True
    started_at: Optional[str] = None
    subject: Optional[str] = Field(default=None, max_length=80)

    @field_validator("started_at")
    @classmethod
    def _iso(cls, value):
        if value and not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
            raise ValueError("开始时间格式应为 YYYY-MM-DDTHH:MM")
        return value


class PlanIn(_Base):
    title: str = Field(min_length=1, max_length=200)
    goal: Optional[str] = Field(default=None, max_length=500)
    start_date: Optional[str] = Field(default=None, pattern=DATE_PATTERN)
    end_date: Optional[str] = Field(default=None, pattern=DATE_PATTERN)

    @model_validator(mode="after")
    def _range(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        return self


class PlanUpdateIn(_Base):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    goal: Optional[str] = Field(default=None, max_length=500)
    start_date: Optional[str] = Field(default=None, pattern=DATE_PATTERN)
    end_date: Optional[str] = Field(default=None, pattern=DATE_PATTERN)
    status: Optional[Literal["active", "completed", "archived"]] = None


class IdsIn(_Base):
    ids: List[int] = Field(min_length=1, max_length=200)


class TaskBatchIn(_Base):
    """批量操作任务：删除，或移动到指定日期 / 顺延 N 天（保留原来的时刻与时长）。"""

    ids: List[int] = Field(min_length=1, max_length=200)
    action: Literal["delete", "move"]
    due_date: Optional[str] = Field(default=None, pattern=DATE_PATTERN)
    shift_days: Optional[int] = Field(default=None, ge=-365, le=365)

    @model_validator(mode="after")
    def _target(self):
        if self.action == "move" and not self.due_date and not self.shift_days:
            raise ValueError("请选择要移动到的日期")
        return self


class ChatTurn(_Base):
    role: Literal["user", "assistant"]
    # 助手回合会带上上一版计划的摘要，所以放宽长度
    content: str = Field(max_length=4000)


class PlanMemory(_Base):
    """多轮对话的结构化记忆：前端原样回传上一轮返回的 memory，追问时在此基础上修改。"""

    subjects: List[str] = Field(default_factory=list, max_length=8)
    start_date: Optional[str] = Field(default=None, pattern=DATE_PATTERN)
    days: Optional[int] = Field(default=None, ge=1, le=31)
    daily_minutes: Optional[int] = Field(default=None, ge=30, le=360)
    prefer: Optional[Literal["morning", "afternoon", "evening"]] = None
    exam: bool = False
    notes: List[str] = Field(default_factory=list, max_length=12)


class AiPlanIn(_Base):
    message: str = Field(min_length=1, max_length=500)
    days: Optional[int] = Field(default=None, ge=1, le=31)
    daily_minutes: Optional[int] = Field(default=None, ge=30, le=360)
    start_date: Optional[str] = Field(default=None, pattern=DATE_PATTERN)
    prefer: Optional[Literal["morning", "afternoon", "evening"]] = None
    use_ai: bool = True
    variant: int = Field(default=0, ge=0, le=20)
    # 最近 10 轮（20 条）对话，助手回合含上一版计划摘要，供模型理解追问
    history: List[ChatTurn] = Field(default_factory=list, max_length=20)
    # 上一轮的结构化记忆（科目、日期范围、时长、偏好、要点），规则引擎和模型都会读取
    memory: Optional[PlanMemory] = None


class DraftTaskIn(_Base):
    date: str = Field(pattern=DATE_PATTERN)
    start_time: Optional[str] = Field(default=None, pattern=TIME_PATTERN)
    duration_minutes: int = Field(ge=5, le=240)
    title: str = Field(min_length=1, max_length=200)
    subject: Optional[str] = Field(default=None, max_length=80)
    priority: int = Field(default=2, ge=0, le=3)
    note: Optional[str] = Field(default=None, max_length=300)


class DraftCourseIn(_Base):
    course_name: str = Field(min_length=1, max_length=160)
    day_of_week: int = Field(ge=1, le=7)
    start_period: int = Field(ge=1, le=16)
    end_period: int = Field(ge=1, le=16)
    weeks: List[int] = Field(min_length=1, max_length=30)
    teacher: Optional[str] = Field(default="", max_length=120)
    classroom: Optional[str] = Field(default="", max_length=80)
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    note: Optional[str] = Field(default="", max_length=200)


class AiCommitIn(_Base):
    title: str = Field(min_length=1, max_length=200)
    goal: Optional[str] = Field(default=None, max_length=500)
    summary: Optional[str] = Field(default=None, max_length=1000)
    advice: Optional[str] = Field(default=None, max_length=4000)
    start_date: str = Field(pattern=DATE_PATTERN)
    end_date: str = Field(pattern=DATE_PATTERN)
    days: int = Field(ge=1, le=31)
    provider: Optional[str] = None
    model: Optional[str] = None
    insights: List[str] = []
    # 31 天 × 每天最多 360 分钟 / 25 分钟一段 ≈ 450，按上限放开
    tasks: List[DraftTaskIn] = Field(default_factory=list, max_length=460)
    courses: List[DraftCourseIn] = Field(default_factory=list, max_length=40)
    import_tasks: bool = True
    import_courses: bool = True

    @model_validator(mode="after")
    def _something_to_import(self):
        if not ((self.import_tasks and self.tasks) or (self.import_courses and self.courses)):
            raise ValueError("计划里没有可导入的任务或课程")
        return self


class AiProviderIn(_Base):
    name: str = Field(min_length=1, max_length=40)
    base_url: str = Field(min_length=8, max_length=300)
    model: str = Field(min_length=1, max_length=120)
    api_key: Optional[str] = Field(default=None, max_length=300)


class AiProviderUpdateIn(_Base):
    name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    base_url: Optional[str] = Field(default=None, min_length=8, max_length=300)
    model: Optional[str] = Field(default=None, min_length=1, max_length=120)
    # 不传或传 null：保留原 Key；传空串：清除 Key
    api_key: Optional[str] = Field(default=None, max_length=300)


class AiProbeIn(_Base):
    """测试连接 / 获取模型列表：可以测已保存的配置（provider_id），也可以测表单里尚未保存的内容。"""

    provider_id: Optional[str] = None
    base_url: Optional[str] = Field(default=None, max_length=300)
    model: Optional[str] = Field(default=None, max_length=120)
    api_key: Optional[str] = Field(default=None, max_length=300)


class AiSettingsIn(_Base):
    active: str = Field(pattern=r"^(auto|rule|\d+)$")
