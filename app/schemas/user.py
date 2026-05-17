"""
用户模型
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    """用户基础模型"""
    username: str
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    """用户创建模型"""
    password: str

class UserLogin(BaseModel):
    """用户登录模型"""
    username: str
    password: str

class UserUpdate(BaseModel):
    """用户更新模型"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None

class UserInDB(UserBase):
    """数据库中的用户模型"""
    id: int
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class User(UserInDB):
    """用户响应模型"""
    pass
 
from app.schemas.token import Token 
from app.schemas.token import Token 
from app.schemas.token import Token 
