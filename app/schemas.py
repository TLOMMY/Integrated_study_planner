from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# 请求模型
class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class PlanGenerateRequest(BaseModel):
    prompt: str
    energy_level: Optional[int] = 5  # 1-10

# 响应模型
class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class MessageResponse(BaseModel):
    code: int
    message: str
    data: Optional[dict] = None

class DataResponse(BaseModel):
    code: int
    message: str
    data: dict
# 追加以下模型

class StudyRecordIn(BaseModel):
    date: str  # YYYY-MM-DD
    focus_minutes: int

class StudyStatsOut(BaseModel):
    total_minutes: int
    today_minutes: int
    streak_days: int
    heatmap_data: dict  # {"2025-04-01": 45, ...}

class PlanGenerateIn(BaseModel):
    prompt: str
    energy_level: int = 5  # 1-10

class PlanOut(BaseModel):
    plan_text: str
    tasks: list  # 结构化任务列表

class CourseIn(BaseModel):
    course_name: str
    weekday: int
    start_time: str
    end_time: str
    location: str = ""

class CalendarEventOut(BaseModel):
    id: int
    title: str
    start: str   # ISO datetime
    end: str
    type: str  # "course" or "task"