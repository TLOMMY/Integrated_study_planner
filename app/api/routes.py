from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from app.db import get_db_connection
from app.schemas import (
    UserRegister, UserLogin, Token, UserOut,
    StudyRecordIn, PlanGenerateIn
)
from app.utils.security import hash_password, verify_password, create_access_token, decode_access_token
from app.utils.response import success_response, error_response
from app.services.game_service import GameService
from app.services.ai_service import AIService
from app.services.import_service import ImportService

router = APIRouter()
security = HTTPBearer()

# ---------- 依赖：获取当前用户 ----------
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT id, username, created_at FROM users WHERE id = ?", (int(user_id),)
        ).fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ---------- 公开路由 ----------
@router.post("/auth/register", response_model=UserOut, status_code=201)
def register(user: UserRegister):
    with get_db_connection() as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (user.username,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username already registered")
        hashed = hash_password(user.password)
        cursor = conn.execute(
            "INSERT INTO users (username, hashed_password) VALUES (?, ?)",
            (user.username, hashed)
        )
        user_id = cursor.lastrowid
        new_user = conn.execute(
            "SELECT id, username, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return new_user

@router.post("/auth/login", response_model=Token)
def login(user: UserLogin):
    with get_db_connection() as conn:
        db_user = conn.execute(
            "SELECT id, username, hashed_password FROM users WHERE username = ?", (user.username,)
        ).fetchone()
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": str(db_user["id"])})
    return {"access_token": access_token, "token_type": "bearer"}

# ---------- 受保护示例路由 ----------
@router.get("/user/me", response_model=UserOut)
def get_current_user_info(current_user=Depends(get_current_user)):
    return current_user

# ---------- 游戏激励接口 ----------
@router.post("/study/record")
async def add_study_record(record: StudyRecordIn, current_user=Depends(get_current_user)):
    GameService.add_study_record(current_user["id"], record.date, record.focus_minutes)
    return success_response(message="专注记录已保存")

@router.get("/study/stats")
async def get_study_stats(current_user=Depends(get_current_user)):
    stats = GameService.get_stats(current_user["id"])
    return success_response(data=stats)

@router.get("/badges")
async def get_my_badges(current_user=Depends(get_current_user)):
    badges = GameService.get_badges(current_user["id"])
    return success_response(data=badges)

# ---------- AI 规划接口 ----------
@router.post("/ai/plan")
async def generate_plan(req: PlanGenerateIn, current_user=Depends(get_current_user)):
    plan = AIService.generate_plan(req.prompt, req.energy_level)
    return success_response(data=plan)

@router.post("/ai/replan")
async def replan(disruption: str, current_user=Depends(get_current_user)):
    new_plan = AIService.reschedule(current_user["id"], disruption)
    return success_response(data=new_plan)

# ---------- 批量导入接口 ----------
@router.post("/import/ocr")
async def import_ocr_timetable(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    contents = await file.read()
    courses = ImportService.ocr_timetable(contents)
    ImportService.save_courses(current_user["id"], courses)
    return success_response(data={"imported": len(courses)})

@router.post("/import/pdf")
async def import_pdf(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    contents = await file.read()
    tasks = ImportService.parse_pdf(contents)
    return success_response(data={"tasks_extracted": len(tasks)})

@router.post("/import/excel")
async def import_excel(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    contents = await file.read()
    courses = ImportService.import_excel(contents)
    ImportService.save_courses(current_user["id"], courses)
    return success_response(data={"imported": len(courses)})

# ---------- 日历数据接口 ----------
@router.get("/calendar/events")
async def get_calendar_events(start: str, end: str, current_user=Depends(get_current_user)):
    """
    获取指定时间范围内的日历事件（课程 + 任务）
    start 和 end 格式: YYYY-MM-DD
    """
    with get_db_connection() as conn:
        # 1. 获取用户的课程（周课表）
        courses = conn.execute("""
                               SELECT id, course_name as title, weekday, start_time, end_time, location
                               FROM courses WHERE user_id = ?
                               """, (current_user["id"],)).fetchall()

        # 2. 获取用户的任务（有具体日期的任务）
        tasks = conn.execute("""
                             SELECT id, title, scheduled_time, duration_minutes
                             FROM tasks
                             WHERE user_id = ? AND date (scheduled_time) BETWEEN ? AND ?
                             """, (current_user["id"], start, end)).fetchall()

    events = []

    # 处理课程：将周课表转换为指定周范围内的具体日期事件
    start_date = datetime.strptime(start, "%Y-%m-%d")
    end_date = datetime.strptime(end, "%Y-%m-%d")
    current = start_date
    # 生成从 start 到 end 的所有日期
    date_range = []
    while current <= end_date:
        date_range.append(current)
        current += timedelta(days=1)

    for course in courses:
        weekday_course = course["weekday"]  # 假设 0=周一, 6=周日（需和前端约定）
        for d in date_range:
            if d.weekday() == weekday_course:  # Python weekday: 0=周一, 6=周日
                event_start = datetime.combine(d, datetime.strptime(course["start_time"], "%H:%M").time())
                event_end = datetime.combine(d, datetime.strptime(course["end_time"], "%H:%M").time())
                events.append({
                    "id": f"course_{course['id']}_{d.isoformat()}",
                    "title": course["title"],
                    "start": event_start.isoformat(),
                    "end": event_end.isoformat(),
                    "type": "course",
                    "location": course["location"]
                })

    # 处理任务
    for task in tasks:
        # 假设 tasks 表中有 scheduled_time (datetime) 字段
        events.append({
            "id": f"task_{task['id']}",
            "title": task["title"],
            "start": task["scheduled_time"],
            "end": None,  # 或计算结束时间 = start + duration_minutes
            "type": "task"
        })

    return success_response(data=events)