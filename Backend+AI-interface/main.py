# -*- coding: utf-8 -*-
"""智能学习规划系统 - 后端入口。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    admin, ai_chat, ai_extras, ai_settings, auth, exams, feedback, imports, planning, social, study, tasks, timetable, users,
)
from app.core.config import DEFAULT_SECRET, settings
from app.core.errors import ok, register_exception_handlers
from app.core.migrate import init_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_database()
    if settings.SECRET_KEY == DEFAULT_SECRET:
        logging.getLogger("study_planner").warning("JWT_SECRET_KEY 仍是开发默认值，部署到服务器前务必在 .env 中改成随机长字符串")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="课表（WakeUp）+ 任务与番茄钟（滴答清单）+ 成长激励（多邻国）。所有接口返回 {code, message, data}。",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)

for module in (auth, users, tasks, timetable, imports, study, ai_settings, feedback, admin, ai_chat, ai_extras, exams, social):
    app.include_router(module.router)
for router in planning.routers:
    app.include_router(router)


@app.get("/", tags=["系统"])
def root():
    return ok({"name": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"})


@app.get("/health", tags=["系统"])
def health():
    return ok({"status": "ok"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
