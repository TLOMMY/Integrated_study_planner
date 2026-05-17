# -*- coding: utf-8 -*-
"""
用户管理路由模块
功能：获取用户信息、更新用户资料
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.schemas.user import User, UserUpdate
from app.core.security import get_current_user
from app.core.database import get_db

router = APIRouter(prefix="/users", tags=["用户"])

@router.get("/me", response_model=User)
async def get_current_user_info(current_user = Depends(get_current_user)):
    """
    获取当前用户信息
    """
    return {
        "id": 1,
        "username": "demo_user",
        "email": "user@example.com",
        "is_active": True
    }

@router.put("/me", response_model=User)
async def update_current_user(
    user_update: UserUpdate,
    current_user = Depends(get_current_user)
):
    """
    更新当前用户信息
    """
    return {
        "id": 1,
        "username": user_update.username or "demo_user",
        "email": user_update.email or "user@example.com",
        "is_active": True
    }

@router.get("/", response_model=List[User])
async def get_all_users():
    """
    获取所有用户（管理员功能）
    """
    return [
        {
            "id": 1,
            "username": "user1",
            "email": "user1@example.com",
            "is_active": True
        }
    ]
