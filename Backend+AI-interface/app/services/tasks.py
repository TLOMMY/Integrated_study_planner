# -*- coding: utf-8 -*-
"""
任务领域逻辑（对标滴答清单）：今日/即将/逾期视图、四级优先级、重复任务、完成回执。
"""

import json
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urlsplit

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import timeutil
from app.core.errors import ApiError
from app.models import StudyPlan, StudyTask, User
from app.services import gamification

PRIORITY_LABELS = {0: "无", 1: "低", 2: "中", 3: "高"}
TRASH_DAYS = 30


def visible_tasks(query):
    """排除回收站里的计划下的任务（计划恢复后任务自动回来）。统计 / XP 等历史数据不受影响。"""
    deleted = select(StudyPlan.id).where(StudyPlan.deleted_at.isnot(None))
    return query.filter(or_(StudyTask.plan_id.is_(None), StudyTask.plan_id.not_in(deleted)))
REPEAT_LABELS = {"none": "不重复", "daily": "每天", "weekdays": "工作日", "weekly": "每周"}


# ---------------------------------------------------------------- v4：标签 / 清单 / 子任务 / 链接 / 提醒
BILIBILI_HOSTS = ("bilibili.com", "b23.tv")


def load_list(raw: Optional[str]) -> list:
    """读取 JSON 数组列；空值或损坏的数据当作空数组，避免一条坏数据让整个列表接口报错。"""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def dump_list(items: Optional[list]) -> Optional[str]:
    return json.dumps(items, ensure_ascii=False) if items else None


def link_source(url: str, source: Optional[str] = None) -> str:
    host = (urlsplit(url).hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in BILIBILI_HOSTS):
        return "bilibili"
    return source or "web"


def clean_checklist(items) -> List[dict]:
    """统一子任务结构 [{id, title, done}]；缺 id 的补一个短 id，重复 id 重新生成。"""
    result, seen = [], set()
    for item in items or []:
        data = item if isinstance(item, dict) else item.model_dump()
        title = str(data.get("title") or "").strip()[:100]
        if not title:
            continue
        item_id = str(data.get("id") or "")[:40]
        if not item_id or item_id in seen:
            item_id = uuid.uuid4().hex[:10]
        seen.add(item_id)
        result.append({"id": item_id, "title": title, "done": bool(data.get("done"))})
    return result


def clean_links(items) -> List[dict]:
    result, seen = [], set()
    for item in items or []:
        data = item if isinstance(item, dict) else item.model_dump()
        url = str(data.get("url") or "").strip()
        if not url or url in seen or urlsplit(url).scheme.lower() not in ("http", "https"):
            continue
        seen.add(url)
        title = str(data.get("title") or "").strip()[:100] or (urlsplit(url).hostname or url)[:100]
        result.append({"title": title, "url": url, "source": link_source(url, data.get("source"))})
    return result


def parse_remind(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def apply_extras(task: StudyTask, changes: dict) -> None:
    """把请求里出现的 v4 字段写到任务上（只处理传入的键，未传的保持不变）。"""
    if "tags" in changes:
        task.tags = dump_list(changes["tags"] or [])
    if "list_name" in changes:
        task.list_name = (changes["list_name"] or "").strip() or None
    if "checklist" in changes:
        task.checklist = dump_list(clean_checklist(changes["checklist"]))
    if "links" in changes:
        task.links = dump_list(clean_links(changes["links"]))
    if "remind_at" in changes:
        task.remind_at = parse_remind(changes["remind_at"])


def task_anchor(task: StudyTask) -> Optional[tuple]:
    """任务的时间锚点 (是否定时, 时间)：有时刻用开始时间，只有日期时用当天 0 点；用于提醒随任务一起平移。"""
    if task.start_time:
        return True, task.start_time
    day = timeutil.parse_date(task.due_date)
    return (False, datetime.combine(day, datetime.min.time())) if day else None


def shift_reminder(task: StudyTask, old_anchor: Optional[tuple]) -> None:
    """改期后提醒时间按同样的偏移平移（例如原来"提前 15 分钟"，改到明天仍是提前 15 分钟）。
    从"只有日期"变成"有具体时刻"（或反过来）时不平移，避免"当天 9:00"被推到奇怪的时间。"""
    new_anchor = task_anchor(task)
    if not (task.remind_at and old_anchor and new_anchor) or old_anchor[0] != new_anchor[0]:
        return
    if old_anchor[1] != new_anchor[1]:
        task.remind_at = task.remind_at + (new_anchor[1] - old_anchor[1])


def task_tags(task: StudyTask) -> List[str]:
    return [str(tag) for tag in load_list(task.tags)]


def tag_like(tag: str) -> str:
    """标签存成 JSON 数组文本，先用 LIKE 粗筛 "标签" 这一段，再在 Python 里精确比对。"""
    token = json.dumps(tag, ensure_ascii=False).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{token}%"


def group_summary(db: Session, user: User) -> dict:
    """清单与标签的使用情况：名称、任务总数、未完成数。按未完成数、名称排序。"""
    rows = visible_tasks(
        db.query(StudyTask.list_name, StudyTask.tags, StudyTask.completed).filter(StudyTask.user_id == user.id)
    ).all()
    lists: Dict[str, dict] = {}
    tags: Dict[str, dict] = {}
    for list_name, raw_tags, done in rows:
        names = [(lists, list_name)] if list_name else []
        names += [(tags, str(tag)) for tag in load_list(raw_tags)]
        for bucket, name in names:
            entry = bucket.setdefault(name, {"name": name, "total": 0, "open": 0})
            entry["total"] += 1
            entry["open"] += 0 if done else 1
    order = lambda items: sorted(items, key=lambda e: (-e["open"], -e["total"], e["name"]))  # noqa: E731
    return {"lists": order(lists.values()), "tags": order(tags.values())}


def rename_group(db: Session, user: User, kind: str, old: str, new: str) -> int:
    """重命名清单 / 标签；新名字已存在时自然合并（标签去重）。返回受影响的任务数。"""
    query = db.query(StudyTask).filter(StudyTask.user_id == user.id)
    if kind == "list":
        return query.filter(StudyTask.list_name == old).update({"list_name": new}, synchronize_session=False)
    count = 0
    for task in query.filter(StudyTask.tags.like(tag_like(old), escape="\\")).all():
        tags = task_tags(task)
        if old not in tags:
            continue
        merged = []
        for tag in tags:
            tag = new if tag == old else tag
            if tag not in merged:
                merged.append(tag)
        task.tags = dump_list(merged)
        count += 1
    return count


def clear_group(db: Session, user: User, kind: str, name: str) -> int:
    """删除清单 / 标签：只把名字从任务上去掉，任务本身保留。"""
    query = db.query(StudyTask).filter(StudyTask.user_id == user.id)
    if kind == "list":
        return query.filter(StudyTask.list_name == name).update({"list_name": None}, synchronize_session=False)
    count = 0
    for task in query.filter(StudyTask.tags.like(tag_like(name), escape="\\")).all():
        tags = task_tags(task)
        if name in tags:
            task.tags = dump_list([tag for tag in tags if tag != name])
            count += 1
    return count


def task_to_dict(task: StudyTask, ref: Optional[date] = None) -> dict:
    ref = ref or timeutil.today()
    checklist = load_list(task.checklist)
    return {
        "id": task.id,
        "plan_id": task.plan_id,
        "plan_title": task.plan.title if task.plan_id and task.plan else None,
        "title": task.title,
        "subject": task.subject or "",
        "note": task.note or "",
        "due_date": task.due_date,
        "start_time": task.start_time.strftime("%H:%M") if task.start_time else None,
        "end_time": task.end_time.strftime("%H:%M") if task.end_time else None,
        "duration_minutes": int(task.duration_minutes or 0),
        "priority": int(task.priority or 0),
        "priority_label": PRIORITY_LABELS.get(int(task.priority or 0), "无"),
        "repeat_rule": task.repeat_rule or "none",
        "repeat_label": REPEAT_LABELS.get(task.repeat_rule or "none", "不重复"),
        "completed": bool(task.completed),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "overdue": bool(not task.completed and task.due_date and task.due_date < ref.isoformat()),
        "focus_minutes": int(task.focus_minutes or 0),
        "pomodoros": int(task.pomodoros or 0),
        "source": task.source or "manual",
        "tags": [str(tag) for tag in load_list(task.tags)],
        "list_name": task.list_name or "",
        "checklist": checklist,
        "checklist_done": sum(1 for item in checklist if isinstance(item, dict) and item.get("done")),
        "checklist_total": len(checklist),
        "links": load_list(task.links),
        "remind_at": task.remind_at.strftime("%Y-%m-%dT%H:%M") if task.remind_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


def get_owned_task(db: Session, user: User, task_id: int) -> StudyTask:
    task = db.query(StudyTask).filter(StudyTask.id == task_id, StudyTask.user_id == user.id).first()
    if task is None:
        raise ApiError(404, "任务不存在或已被删除")
    return task


def get_owned_plan(db: Session, user: User, plan_id: int) -> StudyPlan:
    plan = db.query(StudyPlan).filter(StudyPlan.id == plan_id, StudyPlan.user_id == user.id).first()
    if plan is None:
        raise ApiError(404, "学习计划不存在或已被删除")
    return plan


def apply_schedule(task: StudyTask, due_date: Optional[str], start_hm: Optional[str], duration: int) -> None:
    task.due_date = due_date
    task.duration_minutes = duration
    if due_date and start_hm:
        start_minutes = timeutil.hm_to_minutes(start_hm)
        if start_minutes + duration > 24 * 60:
            raise ApiError(422, "任务不能跨越午夜，请缩短时长或提前开始时间")
        day = date.fromisoformat(due_date)
        task.start_time = timeutil.combine(day, start_hm)
        task.end_time = task.start_time + timedelta(minutes=duration)
    else:
        task.start_time = None
        task.end_time = None


def next_due(rule: str, base: date) -> Optional[date]:
    if rule == "daily":
        return base + timedelta(days=1)
    if rule == "weekly":
        return base + timedelta(days=7)
    if rule == "weekdays":
        candidate = base + timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate
    return None


def spawn_next(db: Session, task: StudyTask) -> Optional[StudyTask]:
    """完成重复任务后生成下一次；补完很久以前的任务时，直接跳到今天以后，避免产生一串逾期。"""
    rule = task.repeat_rule or "none"
    if rule == "none" or not task.due_date:
        return None
    if db.query(StudyTask.id).filter(StudyTask.repeat_parent_id == task.id).first():
        return None
    today = timeutil.today()
    candidate = next_due(rule, date.fromisoformat(task.due_date))
    while candidate is not None and candidate < today:
        candidate = next_due(rule, candidate)
    if candidate is None:
        return None
    child = StudyTask(
        user_id=task.user_id,
        title=task.title,
        subject=task.subject,
        note=task.note,
        priority=task.priority,
        repeat_rule=rule,
        repeat_parent_id=task.id,
        source="repeat",
        status="todo",
        completed=False,
        tags=task.tags,
        list_name=task.list_name,
        # 子任务带到下一次，但全部重置为未完成
        checklist=dump_list([{**item, "done": False} for item in load_list(task.checklist) if isinstance(item, dict)]),
        links=task.links,
        remind_at=task.remind_at,
    )
    apply_schedule(
        child,
        candidate.isoformat(),
        task.start_time.strftime("%H:%M") if task.start_time else None,
        int(task.duration_minutes or 30),
    )
    # 提醒按"距任务开始的偏移"带到下一次
    shift_reminder(child, task_anchor(task))
    db.add(child)
    db.flush()
    return child


def complete_task(db: Session, user: User, task: StudyTask) -> dict:
    tracker = gamification.RewardTracker(db, user)
    spawned = None
    if not task.completed:
        task.completed = True
        task.status = "completed"
        task.completed_at = timeutil.now()
        db.flush()
        xp = gamification.XP_TASK_HIGH if int(task.priority or 0) >= 3 else gamification.XP_TASK
        gamification.award(db, user.id, xp, "task", str(task.id))
        spawned = spawn_next(db, task)
        _check_plan_completion(db, user, task)
    reward = tracker.finish()
    return {"task": task_to_dict(task), "next_task": task_to_dict(spawned) if spawned else None, "reward": reward}


def uncomplete_task(db: Session, user: User, task: StudyTask) -> dict:
    if task.completed:
        task.completed = False
        task.status = "todo"
        task.completed_at = None
        gamification.revoke(db, user.id, "task", str(task.id))
        if task.plan_id and task.plan and task.plan.status == "completed":
            task.plan.status = "active"
            task.plan.completed_at = None
            gamification.revoke(db, user.id, "plan_complete", str(task.plan_id))
        db.flush()
    return {"task": task_to_dict(task), "level": gamification.level_info(gamification.total_xp(db, user.id))}


def _check_plan_completion(db: Session, user: User, task: StudyTask) -> None:
    if not task.plan_id:
        return
    remaining = (
        db.query(StudyTask.id)
        .filter(StudyTask.plan_id == task.plan_id, StudyTask.completed.is_(False))
        .first()
    )
    plan = task.plan
    if remaining is None and plan is not None and plan.status != "completed":
        plan.status = "completed"
        plan.completed_at = timeutil.now()
        gamification.award(db, user.id, gamification.XP_PLAN_COMPLETE, "plan_complete", str(plan.id))


def task_counts(db: Session, user: User, ref: date) -> Dict[str, int]:
    key = ref.isoformat()
    rows = visible_tasks(db.query(StudyTask.due_date, StudyTask.completed).filter(StudyTask.user_id == user.id)).all()
    counts = {"today": 0, "today_done": 0, "overdue": 0, "upcoming": 0, "completed": 0}
    for due, done in rows:
        if done:
            counts["completed"] += 1
        if due == key:
            counts["today"] += 1
            counts["today_done"] += 1 if done else 0
        elif not done and due and due < key:
            counts["overdue"] += 1
        elif not done and (not due or due > key):
            counts["upcoming"] += 1
    return counts


# ---------------------------------------------------------------- 学习计划
PLAN_STATUS_LABELS = {"active": "进行中", "completed": "已完成", "archived": "已归档"}


def purge_trash(db: Session, user: User) -> int:
    """回收站里超过 30 天的计划彻底删除（连同任务；专注记录保留，只解除关联）。"""
    from app.models import FocusRecord

    cutoff = timeutil.now() - timedelta(days=TRASH_DAYS)
    expired = db.query(StudyPlan).filter(StudyPlan.user_id == user.id, StudyPlan.deleted_at.isnot(None),
                                         StudyPlan.deleted_at < cutoff).all()
    for plan in expired:
        hard_delete_plan(db, plan)
    return len(expired)


def hard_delete_plan(db: Session, plan: StudyPlan) -> int:
    from app.models import FocusRecord

    task_ids = [task.id for task in plan.tasks]
    if task_ids:
        db.query(FocusRecord).filter(FocusRecord.task_id.in_(task_ids)).update({"task_id": None}, synchronize_session=False)
    db.delete(plan)
    return len(task_ids)


def plan_to_dict(plan: StudyPlan, include_tasks: bool = False) -> dict:
    tasks = list(plan.tasks or [])
    total = len(tasks)
    done = sum(1 for task in tasks if task.completed)
    today = timeutil.today()
    start = timeutil.parse_date(plan.start_date) or (plan.created_at.date() if plan.created_at else today)
    end = timeutil.parse_date(plan.end_date) or start + timedelta(days=max(1, int(plan.duration_days or 7)) - 1)
    remaining = (end - today).days
    data = {
        "id": plan.id,
        "title": plan.title,
        "goal": plan.goal or "",
        "description": plan.description or "",
        "status": plan.status or "active",
        "status_label": PLAN_STATUS_LABELS.get(plan.status or "active", "进行中"),
        "source": plan.source or "manual",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "duration_days": (end - start).days + 1,
        "remaining_days": max(0, remaining),
        "expired": remaining < 0 and plan.status == "active",
        "task_total": total,
        "task_done": done,
        "progress": round(done / total * 100) if total else 0,
        "focus_minutes": sum(int(task.focus_minutes or 0) for task in tasks),
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "deleted_at": plan.deleted_at.isoformat() if plan.deleted_at else None,
        "purge_in_days": max(0, TRASH_DAYS - (timeutil.now() - plan.deleted_at).days) if plan.deleted_at else None,
    }
    if include_tasks:
        ordered = sorted(tasks, key=lambda t: (t.due_date or "9999", t.start_time or timeutil.combine(today, "23:59"), t.id))
        data["tasks"] = [task_to_dict(task) for task in ordered]
    return data
