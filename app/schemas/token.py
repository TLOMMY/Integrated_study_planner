"""
令牌模型
用于JWT认证
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Token(BaseModel):
    """访问令牌模型"""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """令牌数据"""
    username: Optional[str] = None

class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    token_type: str
    expires_in: int = 3600
    refresh_token: Optional[str] = None
