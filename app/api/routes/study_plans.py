# -*- coding: utf-8 -*-
"""
学习计划路由模块
功能：学习计划的CRUD操作
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime

from app.schemas.study_plan import StudyPlanCreate, StudyPlanResponse, StudyPlanUpdate
from app.core.security import get_current_user
from app.core.database import get_db

router = APIRouter(prefix="/study-plans", tags=["学习计划"])

@router.post("/", response_model=StudyPlanResponse)
async def create_study_plan(
    plan_data: StudyPlanCreate,
    current_user = Depends(get_current_user)
):
    """
    创建学习计划
    """
    return {
        "id": 1,
        "user_id": 1,
        "title": plan_data.title or "默认学习计划",
        "description": plan_data.description or "计划描述",
        "created_at": datetime.now().isoformat(),
        "status": "active"
    }

@router.get("/", response_model=List[StudyPlanResponse])
async def get_study_plans(current_user = Depends(get_current_user)):
    """
    获取用户的所有学习计划
    """
    return [
        {
            "id": 1,
            "user_id": 1,
            "title": "Python学习计划",
            "description": "学习Python编程",
            "created_at": "2026-04-20T10:00:00",
            "status": "active"
        }
    ]

@router.get("/{plan_id}", response_model=StudyPlanResponse)
async def get_study_plan(plan_id: int, current_user = Depends(get_current_user)):
    """
    获取特定学习计划
    """
    return {
        "id": plan_id,
        "user_id": 1,
        "title": f"学习计划 {plan_id}",
        "description": "计划详情",
        "created_at": "2026-04-20T10:00:00",
        "status": "active"
    }

@router.put("/{plan_id}", response_model=StudyPlanResponse)
async def update_study_plan(
    plan_id: int,
    plan_update: StudyPlanUpdate,
    current_user = Depends(get_current_user)
):
    """
    更新学习计划
    """
    return {
        "id": plan_id,
        "user_id": 1,
        "title": plan_update.title or f"更新后的计划 {plan_id}",
        "description": plan_update.description or "更新后的描述",
        "created_at": "2026-04-20T10:00:00",
        "updated_at": datetime.now().isoformat(),
        "status": "active"
    }

@router.delete("/{plan_id}")
async def delete_study_plan(plan_id: int, current_user = Depends(get_current_user)):
    """
    删除学习计划
    """
    return {"message": f"学习计划 {plan_id} 已删除", "success": True}
