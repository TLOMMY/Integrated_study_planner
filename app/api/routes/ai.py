# -*- coding: utf-8 -*-
"""
AI路由模块
简化版本，避免依赖问题
"""

from fastapi import APIRouter
from typing import Dict, Any

# 创建路由
router = APIRouter(prefix="/ai", tags=["AI规划"])

@router.get("/health")
async def ai_health():
    """AI模块健康检查"""
    return {
        "status": "healthy",
        "module": "AI规划器",
        "version": "1.0.0"
    }

@router.post("/generate-plan")
async def generate_plan():
    """生成学习计划（简化版）"""
    return {
        "status": "success",
        "message": "AI规划器就绪，请配置API密钥",
        "plan": {
            "goal": "示例学习目标",
            "duration": "1周",
            "tasks": ["任务1", "任务2", "任务3"]
        }
    }

@router.get("/energy-level")
async def get_energy_level():
    """获取精力等级"""
    return {
        "energy_level": "medium",
        "recommendation": "精力适中，适合学习"
    }
