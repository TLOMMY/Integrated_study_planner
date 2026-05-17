# -*- coding: utf-8 -*-
from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware 
from app.api.routes import auth, users, study_plans, ai 
 
app = FastAPI(title="智能学习规划系统(整合版)", version="2.0.0") 
 
# 配置CORS 
app.add_middleware( 
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"], 
) 
 
# 包含路由 
app.include_router(auth.router) 
app.include_router(users.router) 
app.include_router(study_plans.router) 
app.include_router(ai.router) 
 
@app.get("/") 
async def root(): 
    return { 
        "project": "智能学习规划系统(整合版)", 
        "version": "2.0.0", 
        "modules": ["认证", "用户管理", "学习计划", "AI规划"] 
    } 
 
if __name__ == "__main__": 
    import uvicorn 
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 
