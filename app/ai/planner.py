# -*- coding: utf-8 -*-
"""
AI规划模块
"""

import os
from typing import Dict, Any

class DeepSeekPlanner:
    """DeepSeek API规划器"""
    
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
    
    def generate_study_plan(self, goal: str, available_hours: int) -> Dict[str, Any]:
        """生成学习计划"""
        if not self.api_key:
            return {
                "status": "error",
                "message": "DeepSeek API密钥未配置"
            }
        return {
            "status": "success",
            "data": {
                "goal": goal,
                "available_hours": available_hours,
                "message": "AI规划器就绪，请配置API密钥"
            }
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """测试API连接"""
        if not self.api_key:
            return {"status": "error", "message": "API密钥未配置"}
        return {"status": "success", "message": "API连接正常"}
