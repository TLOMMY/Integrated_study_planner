"""
学习计划模型
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class StudyPlanBase(BaseModel):
    """学习计划基础模型"""
    title: str
    description: Optional[str] = None
    goal: str
    available_hours: int
    duration_days: int = 7
    difficulty: str = "medium"

class StudyPlanCreate(StudyPlanBase):
    """学习计划创建模型"""
    pass

class StudyPlanUpdate(BaseModel):
    """学习计划更新模型"""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    content: Optional[Dict[str, Any]] = None

class StudyPlanInDB(StudyPlanBase):
    """数据库中的学习计划模型"""
    id: int
    user_id: int
    status: str = "active"
    content: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class StudyPlanResponse(StudyPlanInDB):
    """学习计划响应模型"""
    pass

class StudyPlanList(BaseModel):
    """学习计划列表响应"""
    plans: List[StudyPlanResponse]
    total: int
    page: int
    per_page: int


# 别名，兼容旧代码
StudyPlan = StudyPlanInDB