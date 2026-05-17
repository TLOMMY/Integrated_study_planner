# -*- coding: utf-8 -*-
"""
应用配置 - 简化版
避免pydantic-settings验证问题
"""

import os
from typing import Optional

class Settings:
    """应用配置类"""
    
    def __init__(self):
        # 应用配置
        self.APP_NAME = "智能学习规划系统"
        self.APP_VERSION = "1.0.0"
        self.DEBUG = os.getenv("DEBUG", "True").lower() in ["true", "1", "yes"]
        
        # API配置
        self.API_V1_STR = "/api/v1"
        
        # 数据库配置
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./study_planner.db")
        
        # JWT配置
        self.SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
        self.ALGORITHM = os.getenv("ALGORITHM", "HS256")
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
        
        # AI配置
        self.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
        
        # 添加缺失的字段
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", self.SECRET_KEY)
        self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", self.SECRET_KEY)  # 兼容小写

# 创建配置实例
settings = Settings()

# 打印配置信息
if __name__ == "__main__":
    print("配置信息:")
    print(f"应用: {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"数据库: {settings.DATABASE_URL}")
    print(f"JWT密钥: {settings.SECRET_KEY[:10]}...")
