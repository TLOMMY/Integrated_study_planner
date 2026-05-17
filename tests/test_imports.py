# -*- coding: utf-8 -*-
"""
Created on Sun Apr 19 20:51:47 2026

@author: Latte
"""

# test_imports.py
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.getcwd())

print("测试模块导入...")
print("="*60)

modules_to_test = [
    ("app.core.config", "配置模块"),
    ("app.core.database", "数据库模块"),
    ("app.core.security", "安全模块"),
    ("app.api.routes.auth", "认证路由"),
    ("app.api.routes.users", "用户路由"),
    ("app.api.routes.study_plans", "学习计划路由"),
    ("app.api.routes.ai", "AI路由"),
    ("app.ai.planner", "AI规划器")
]

for module_path, description in modules_to_test:
    try:
        __import__(module_path)
        print(f"✅ {description}: 导入成功")
    except Exception as e:
        print(f"❌ {description}: 导入失败 - {e}")

print("\n" + "="*60)
print("导入测试完成！")