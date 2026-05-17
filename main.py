from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import router
from app.db import init_db
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.utils.response import error_response

app = FastAPI(title="智能学习规划系统", version="1.0")

# CORS 配置（开发阶段允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 生产环境请限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据库（启动时自动创建表）
@app.on_event("startup")
def startup_event():
    init_db()
    print("Database initialized.")

# 挂载路由
app.include_router(router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Study Planner API is running", "docs": "/docs"}

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return error_response(f"参数错误: {exc.errors()}", code=422)

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return error_response(f"服务器内部错误: {str(exc)}", code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
