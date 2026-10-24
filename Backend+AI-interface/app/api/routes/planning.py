# -*- coding: utf-8 -*-
"""学习计划、AI 规划、日视图、首页汇总。"""

from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter

from app.ai import planner, providers
from app.api.deps import DB, CurrentUser
from app.core import timeutil
from app.core.errors import ApiError, ok
from app.models import FocusRecord, StudyPlan
from app.schemas import AiCommitIn, AiPlanIn, IdsIn, PlanIn, PlanUpdateIn
from app.services import agenda, gamification
from app.services.tasks import get_owned_plan, hard_delete_plan, plan_to_dict, purge_trash

plans_router = APIRouter(prefix="/study-plans", tags=["学习计划"])
ai_router = APIRouter(prefix="/ai", tags=["AI 规划"])
day_router = APIRouter(prefix="/day", tags=["日程"])
home_router = APIRouter(prefix="/home", tags=["首页"])


# ---------------------------------------------------------------- 学习计划
@plans_router.get("", summary="计划列表（status=trash 查看回收站）")
def list_plans(user: CurrentUser, db: DB,
               status: Literal["active", "completed", "archived", "all", "trash"] = "all"):
    if purge_trash(db, user):
        db.commit()
    plans = db.query(StudyPlan).filter(StudyPlan.user_id == user.id).order_by(StudyPlan.id.desc()).all()
    live = [p for p in plans if p.deleted_at is None]
    trash = sorted((p for p in plans if p.deleted_at is not None), key=lambda p: p.deleted_at, reverse=True)
    counts = {key: sum(1 for p in live if (p.status or "active") == key) for key in ("active", "completed", "archived")}
    counts["trash"] = len(trash)
    if status == "trash":
        items = trash
    elif status == "all":
        items = live
    else:
        items = [p for p in live if (p.status or "active") == status]
    return ok({"items": [plan_to_dict(p) for p in items], "total": len(items), "counts": counts})


def _owned_many(db, user, ids, in_trash: bool):
    plans = db.query(StudyPlan).filter(StudyPlan.user_id == user.id, StudyPlan.id.in_(ids)).all()
    plans = [p for p in plans if (p.deleted_at is not None) == in_trash]
    if not plans:
        raise ApiError(404, "没有找到要操作的计划，请刷新后重试")
    return plans


@plans_router.post("/trash/restore", summary="从回收站恢复（可多选）")
def restore_plans(payload: IdsIn, user: CurrentUser, db: DB):
    plans = _owned_many(db, user, payload.ids, in_trash=True)
    for plan in plans:
        plan.deleted_at = None
    db.commit()
    return ok({"ids": [p.id for p in plans], "count": len(plans)}, f"已恢复 {len(plans)} 个计划")


@plans_router.post("/trash/purge", summary="在回收站中彻底删除（可多选，不可恢复）")
def purge_plans(payload: IdsIn, user: CurrentUser, db: DB):
    plans = _owned_many(db, user, payload.ids, in_trash=True)
    tasks = sum(hard_delete_plan(db, plan) for plan in plans)
    db.commit()
    return ok({"ids": [p.id for p in plans], "count": len(plans), "deleted_tasks": tasks}, f"已彻底删除 {len(plans)} 个计划")


@plans_router.delete("/trash", summary="清空回收站（不可恢复）")
def empty_trash(user: CurrentUser, db: DB):
    plans = db.query(StudyPlan).filter(StudyPlan.user_id == user.id, StudyPlan.deleted_at.isnot(None)).all()
    tasks = sum(hard_delete_plan(db, plan) for plan in plans)
    db.commit()
    return ok({"count": len(plans), "deleted_tasks": tasks}, "回收站已清空" if plans else "回收站本来就是空的")


@plans_router.get("/{plan_id}", summary="计划详情（含任务）")
def plan_detail(plan_id: int, user: CurrentUser, db: DB):
    return ok(plan_to_dict(get_owned_plan(db, user, plan_id), include_tasks=True))


@plans_router.post("", summary="创建计划")
def create_plan(payload: PlanIn, user: CurrentUser, db: DB):
    tracker = gamification.RewardTracker(db, user)
    start = payload.start_date or timeutil.today().isoformat()
    end = payload.end_date or (timeutil.parse_date(start) + timedelta(days=6)).isoformat()
    plan = StudyPlan(user_id=user.id, title=payload.title, goal=payload.goal, start_date=start, end_date=end,
                     duration_days=(timeutil.parse_date(end) - timeutil.parse_date(start)).days + 1,
                     status="active", source="manual")
    db.add(plan)
    db.flush()
    reward = tracker.finish()
    db.commit()
    db.refresh(plan)
    return ok({"plan": plan_to_dict(plan, include_tasks=True), "reward": reward}, "计划已创建")


@plans_router.put("/{plan_id}", summary="修改计划")
def update_plan(plan_id: int, payload: PlanUpdateIn, user: CurrentUser, db: DB):
    plan = get_owned_plan(db, user, plan_id)
    if plan.deleted_at is not None:
        raise ApiError(409, "计划在回收站里，请先恢复再修改")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(plan, field, value)
    if plan.start_date and plan.end_date:
        if plan.end_date < plan.start_date:
            raise ApiError(422, "结束日期不能早于开始日期")
        plan.duration_days = (timeutil.parse_date(plan.end_date) - timeutil.parse_date(plan.start_date)).days + 1
    if changes.get("status") == "completed" and not plan.completed_at:
        plan.completed_at = timeutil.now()
    elif changes.get("status") == "active":
        plan.completed_at = None
    db.commit()
    db.refresh(plan)
    return ok(plan_to_dict(plan, include_tasks=True), "计划已更新")


@plans_router.delete("/{plan_id}", summary="删除计划：移入回收站（其中的任务一并隐藏），30 天后自动彻底删除")
def delete_plan(plan_id: int, user: CurrentUser, db: DB):
    plan = get_owned_plan(db, user, plan_id)
    if plan.deleted_at is None:
        plan.deleted_at = timeutil.now()
        db.commit()
    return ok({"id": plan_id, "hidden_tasks": len(plan.tasks)}, "已移入回收站，30 天内可恢复")


# ---------------------------------------------------------------- AI
@ai_router.get("/health", summary="当前使用的模型")
def ai_health(user: CurrentUser, db: DB):
    return ok(providers.active_info(db, user))


@ai_router.post("/plan", summary="生成草稿（不写库）：advice 学习建议 + tasks/courses 结构化计划")
def ai_plan(payload: AiPlanIn, user: CurrentUser, db: DB):
    draft = planner.generate_draft(db, user, payload.message, days=payload.days, daily_minutes=payload.daily_minutes,
                                   start_date=payload.start_date, prefer=payload.prefer, use_ai=payload.use_ai,
                                   variant=payload.variant, history=[t.model_dump() for t in payload.history],
                                   memory=payload.memory.model_dump() if payload.memory else None)
    return ok(draft, "计划草稿已生成")


@ai_router.post("/plan/commit", summary="采纳草稿：任务写入新计划，课程写入课表（冲突课程跳过）")
def ai_commit(payload: AiCommitIn, user: CurrentUser, db: DB):
    tracker = gamification.RewardTracker(db, user)
    result = planner.commit_draft(db, user, payload.model_dump())
    reward = tracker.finish()
    db.commit()
    plan = result["plan"]
    if plan is not None:
        db.refresh(plan)
    parts = []
    if plan is not None:
        parts.append(f"{plan_to_dict(plan)['task_total']} 个任务")
    if result["courses_saved"]:
        parts.append(f"{len(result['courses_saved'])} 门课程")
    return ok(
        {
            "plan": plan_to_dict(plan, include_tasks=True) if plan is not None else None,
            "courses_saved": result["courses_saved"],
            "courses_skipped": result["courses_skipped"],
            "reward": reward,
        },
        f"已加入：{'、'.join(parts) or '无'}",
    )


# ---------------------------------------------------------------- 日视图 / 首页
@day_router.get("/timeline", summary="某天的时间轴：课程 + 定时任务 + 空闲时段")
def day_timeline(user: CurrentUser, db: DB, date: Optional[str] = None):
    return ok(agenda.build_day(db, user, timeutil.parse_date(date, timeutil.today())))


@home_router.get("/summary", summary="首页汇总：问候、下一节课、今日进度、连续打卡、等级")
def home_summary(user: CurrentUser, db: DB, date: Optional[str] = None):
    return ok(agenda.home_summary(db, user, timeutil.parse_date(date, timeutil.today())))


# 供 main.py 统一注册
routers = [plans_router, ai_router, day_router, home_router]
