# -*- coding: utf-8 -*-
"""
AI 学习智能体：工具调用 + 流式输出 + 提案确认。

一轮对话（run_turn）：
  1. 模型按需调用读工具（今天/教学周/节次表/偏好/考试、课程、任务、空闲时段、联网搜索）；
  2. 写操作一律不直接执行，而是调用 propose_* 产出"提案"（新任务 / 新课程 / 修改已有内容），
     信息不足时调用 ask_user 追问（可带选项）；
  3. 用户在界面上编辑、勾选提案后调用 apply_proposal，逐条校验、逐条应用，返回每条成功 / 失败原因。

降级：模型不支持 tools（400/422）→ 旧的 JSON 草稿流程（planner.generate_draft）；
      没有配置模型 → 本地规则引擎生成任务提案，课程创建 / 修改已有内容给出友好说明。

run_turn 是生成器：yield 事件字典 {"event": ..., "data": ...}，过程中把结果写进 TurnState，
即使客户端中途断开，路由也能把已生成的部分保存下来。
"""

import json
import logging
import re
import uuid
from datetime import date, timedelta
from typing import Dict, Iterator, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.ai import llm, planner, providers
from app.core import timeutil
from app.core.errors import ApiError
from app.models import ChatMessage, Exam, FocusRecord, StudyPlan, StudyTask, Timetable, User
from app.services import prefs as prefs_service
from app.services import schedule
from app.services.tasks import PRIORITY_LABELS, apply_schedule, get_owned_plan, visible_tasks

try:  # 联网搜索由代理 F 实现；模块缺失或出错时不影响其他工具
    from app.ai import search as search_tools
except Exception:  # noqa: BLE001
    search_tools = None

logger = logging.getLogger("study_planner.agent")

MAX_STEPS = 6
HISTORY_LIMIT = 24
REASONING_KEEP = 600
MAX_ITEMS = 120
WEEK_CN = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
MEALS = (("12:00", "13:30", "午饭"), ("17:30", "18:30", "晚饭"))

SYSTEM_PROMPT = """你是「学业管家」里的 AI 学习助手，服务对象是中国大学生。你能读取这位同学的课表、任务、空闲时段和学习偏好，帮他答疑、做学习规划、维护课表和日程。

## 基本事实
- 时间一律按北京时间（Asia/Shanghai）。今天的日期、星期、教学周、节次表、学习偏好、近期考试都要先调用 get_context 获取，不要自己猜日期。
- 同学的课程和任务只能通过 list_courses / list_tasks / get_free_slots 查询，绝不编造不存在的课程、任务或 id。
- 你没有直接修改数据的权限。新建或修改任何东西，都必须调用 propose_tasks / propose_courses / propose_changes 生成"提案卡片"，同学在卡片上确认后才会导入。所以回复里要说"已为你生成，确认后导入"，不能说"已添加 / 已修改"。

## 先判断意图
1. 普通问答（如"线代怎么复习""这个概念是什么意思"）：直接用你的知识回答，不要调用任何提案工具，不要硬塞计划。
2. 新建学习任务 / 复习计划 / 作业安排：调用 propose_tasks。
3. 往课表里加课程（每周固定星期、固定节次、按周次上课的课，如"周四 11-12 节数据库，1-16 周"）：调用 propose_courses。课程和任务不同：课程是每周重复的固定课，任务是某一天某个时段的学习块。
4. 修改或删除已有的任务 / 课程（改时间、改日期、改时长、改标题或优先级、删除、整天挪动、改课程的节次 / 星期 / 教室 / 周次）：先用 list_tasks 或 list_courses 找到真实 id，再调用 propose_changes。
5. 一句话里同时有多种意图（比如既要加课又要排复习），分别调用对应的提案工具，同时给出两类提案。

## 什么时候追问
- 只有当关键信息缺失、会明显影响结果、而且无法通过工具查到时，才调用 ask_user。一次只问最关键的 1-2 点，尽量给 2-4 个可点选的短选项。调用 ask_user 后本轮结束，等同学回答。
- 能用合理默认值的就不要问：学习块默认 45 分钟、每天 1-2 小时、"这周"指今天到本周日、时段按 get_context 里的学习偏好。
- 必须问的情况举例：要排复习但完全不知道科目，或不清楚复习到什么程度、是否临近考试；加课缺星期或节次（缺周次时默认整学期，缺教室 / 老师留空即可）；要改的任务有多个都可能匹配且无法判断。

## 排任务的规则
- 先调用 get_free_slots 查目标日期的空闲时段，只在空闲时段内安排：不能和课程、已有任务重叠，不能跨午夜，不早于偏好的最早时间、不晚于最晚时间，避开午饭和晚饭。
- 每个学习块 20-120 分钟，块与块之间留 5-10 分钟休息；标题写成"科目：具体内容"，note 写一句可执行的提示。
- 临近考试（get_context.exams）的科目优先、优先级更高；难的内容放在同学精力好的时段。
- 同学想要网课 / 视频 / 资料推荐时，用搜索工具查找，只把真实搜到的链接放进对应任务的 links，绝不编造网址。
- propose_tasks 返回 issues（冲突、时间已过等）时，调整后重新调用 propose_tasks（会替换上一张卡片）；只有 warnings 时不必重排。

## 修改已有内容的规则
- 只用工具查到的真实 id。每条修改只填需要变动的字段，并写清原因。
- "把明天的任务都往后挪一天"这类整天挪动：对当天每个任务分别提交一条修改日期的 update。删除用 action=delete。

## 回复风格
- 简体中文，像靠谱的学长学姐：先用 1-3 句话给出结论或建议，再说明提案卡片里有什么，不要把每个任务逐条复述（卡片上已经有）。
- 简洁，可用短段落和列表，不用表格；不要输出 JSON、工具名或内部 id。
- 调用工具之前不要写过渡性的话（如"我来查一下"）；结论只在最后一次回复里写一遍，不要前后重复。
- 生成提案后提醒一句：可以直接在卡片上修改日期、开始时间、时长或取消勾选，再点导入。"""


# ---------------------------------------------------------------- 工具定义（OpenAI function calling）
def _fn(name: str, description: str, properties: dict, required: Optional[List[str]] = None) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": required or []}}}


_DATE = {"type": "string", "description": "YYYY-MM-DD"}
_TIME = {"type": "string", "description": "HH:MM，24 小时制"}
_LINK = {"type": "object", "properties": {"title": {"type": "string"}, "url": {"type": "string"},
                                          "source": {"type": "string", "description": "来源，如 bilibili"}},
         "required": ["title", "url"]}
_TASK_ITEM = {"type": "object", "properties": {
    "date": _DATE, "start_time": _TIME,
    "duration_minutes": {"type": "integer", "description": "20-120"},
    "title": {"type": "string", "description": "科目：具体内容"},
    "subject": {"type": "string"},
    "priority": {"type": "integer", "description": "0 无 / 1 低 / 2 中 / 3 高"},
    "note": {"type": "string", "description": "一句执行提示"},
    "links": {"type": "array", "items": _LINK, "description": "搜索到的真实学习资源链接，没有就不填"},
}, "required": ["date", "start_time", "duration_minutes", "title"]}
_COURSE_ITEM = {"type": "object", "properties": {
    "course_name": {"type": "string"},
    "day_of_week": {"type": "integer", "description": "1=周一 … 7=周日"},
    "start_period": {"type": "integer"}, "end_period": {"type": "integer"},
    "weeks": {"type": "array", "items": {"type": "integer"}, "description": "上课周次列表，不填表示整学期"},
    "week_text": {"type": "string", "description": "也可以写成 1-16周 / 2-16周(双)"},
    "classroom": {"type": "string"}, "teacher": {"type": "string"},
}, "required": ["course_name", "day_of_week", "start_period", "end_period"]}
_CHANGE_ITEM = {"type": "object", "properties": {
    "target": {"type": "string", "enum": ["task", "course"]},
    "id": {"type": "integer", "description": "list_tasks / list_courses 返回的真实 id"},
    "action": {"type": "string", "enum": ["update", "delete"]},
    "changes": {"type": "object", "description": (
        "只填要改的字段。任务：date、start_time、duration_minutes、title、subject、priority、note；"
        "课程：course_name、day_of_week、start_period、end_period、weeks、week_text、classroom、teacher")},
    "reason": {"type": "string"},
}, "required": ["target", "id", "action"]}

CORE_TOOLS: List[dict] = [
    _fn("get_context", "获取今天的日期与星期、当前时间、教学周、节次时间表、学习时段偏好、近期考试。每轮对话涉及日期时先调用。", {}),
    _fn("list_courses", "列出本学期课表里的全部课程（含 id、星期、节次、周次、教室）。", {}),
    _fn("list_tasks", "按日期区间查询已有任务（含 id、日期、时间、时长、是否完成）。", {
        "start": _DATE, "end": _DATE,
        "query": {"type": "string", "description": "可选，按标题 / 科目 / 备注搜索"},
        "include_completed": {"type": "boolean"}}, ["start", "end"]),
    _fn("get_free_slots", "查询日期区间内每天的课程、已定时任务和可用于学习的空闲时段（已避开课程、已有任务、饭点和偏好外的时间）。最多 14 天。", {
        "start": _DATE, "end": _DATE}, ["start", "end"]),
    _fn("propose_tasks", "生成【新建任务】提案卡片（不会直接写入，需同学确认导入）。同一轮再次调用会替换上一张任务卡片。", {
        "title": {"type": "string", "description": "这组任务的计划名，不超过 20 字"},
        "summary": {"type": "string", "description": "一句话说明"},
        "items": {"type": "array", "items": _TASK_ITEM}}, ["items"]),
    _fn("propose_courses", "生成【新增课程到课表】提案卡片（每周固定上课的课程）。", {
        "items": {"type": "array", "items": _COURSE_ITEM}}, ["items"]),
    _fn("propose_changes", "生成【修改 / 删除已有任务或课程】提案卡片，会显示修改前→修改后对比。", {
        "summary": {"type": "string"},
        "items": {"type": "array", "items": _CHANGE_ITEM}}, ["items"]),
    _fn("ask_user", "信息不足时向同学追问。一次只问 1-2 个最关键的问题，尽量给 2-4 个短选项。调用后本轮结束。", {
        "question": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}, "description": "可点选的短选项，每个不超过 20 字"}},
        ["question"]),
]

TOOL_LABELS = {
    "get_context": "读取今天与学期信息",
    "list_courses": "查看课表",
    "list_tasks": "查看已有任务",
    "get_free_slots": "计算空闲时段",
    "propose_tasks": "生成任务提案",
    "propose_courses": "生成课程提案",
    "propose_changes": "生成修改提案",
    "ask_user": "追问",
}


def _search_tools() -> List[dict]:
    """联网搜索工具（代理 F）：优先用 available_tools()（尊重管理员的 AI_WEB_SEARCH 开关）。"""
    if search_tools is None:
        return []
    try:
        getter = getattr(search_tools, "available_tools", None)
        return list(getter() if callable(getter) else getattr(search_tools, "TOOLS", None) or [])
    except Exception:  # noqa: BLE001
        return []


def tool_definitions() -> List[dict]:
    return CORE_TOOLS + _search_tools()


# ---------------------------------------------------------------- 小工具
def _hm(value) -> Optional[str]:
    """把 "9:00" / "09:00:00" 规范成 "09:00"；不合法返回 None。"""
    match = re.match(r"^\s*(\d{1,2})[:：](\d{2})", str(value or ""))
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return None
    return f"{hours:02d}:{minutes:02d}"


def _int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _md(day: str) -> str:
    parsed = timeutil.parse_date(day)
    return f"{parsed.month}/{parsed.day}{timeutil.weekday_label(parsed)}" if parsed else str(day)


def _end_hm(start: str, minutes: int) -> str:
    return timeutil.minutes_to_hm(timeutil.hm_to_minutes(start) + minutes)


def _note_with_links(note: Optional[str], links: List[dict]) -> Optional[str]:
    """把搜索到的学习资源追加到备注末尾：每行「· 标题 网址」，前端会把网址显示成可点的链接。"""
    lines = [str(note).strip()] if note and str(note).strip() else []
    if links:
        lines.append("学习资源：")
        lines += [f"· {link['title']} {link['url']}" for link in links]
    text = "\n".join(lines)
    return text[:2000] or None


def _clean_links(raw) -> List[dict]:
    links = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not re.match(r"^https?://\S+$", url, re.I) or len(url) > 500:
            continue
        links.append({"title": str(item.get("title") or url).strip()[:120],
                      "url": url, "source": str(item.get("source") or "").strip()[:30]})
        if len(links) >= 5:
            break
    return links


def _short_id() -> str:
    return uuid.uuid4().hex[:10]


def _task_snapshot(task: StudyTask) -> dict:
    return {
        "date": task.due_date,
        "start_time": task.start_time.strftime("%H:%M") if task.start_time else None,
        "duration_minutes": int(task.duration_minutes or 30),
        "title": task.title,
        "subject": task.subject or "",
        "priority": int(task.priority or 0),
        "note": task.note or "",
    }


def _course_snapshot(user: User, course: Timetable) -> dict:
    total = int(user.total_weeks or 20)
    weeks = schedule.course_weeks(course, total)
    return {
        "course_name": course.course_name,
        "day_of_week": course.day_of_week,
        "start_period": course.start_period or schedule.time_to_period(user, course.start_time),
        "end_period": course.end_period or schedule.time_to_period(user, course.end_time, use_end=True),
        "weeks": weeks,
        "week_text": course.week_text or schedule.format_weeks(weeks),
        "classroom": course.classroom or "",
        "teacher": course.teacher or "",
    }


def _task_line(snap: dict) -> str:
    when = _md(snap.get("date")) if snap.get("date") else "无日期"
    if snap.get("start_time"):
        when += f" {snap['start_time']}-{_end_hm(snap['start_time'], int(snap.get('duration_minutes') or 30))}"
    return when


def _course_line(snap: dict) -> str:
    return f"{WEEK_CN[int(snap['day_of_week'])] if 1 <= int(snap['day_of_week'] or 0) <= 7 else '?'} " \
           f"{snap['start_period']}-{snap['end_period']}节"


def _task_diff(before: dict, after: dict) -> List[dict]:
    diff = []
    if (before["date"], before["start_time"], before["duration_minutes"]) != \
            (after["date"], after["start_time"], after["duration_minutes"]):
        diff.append({"field": "时间", "before": _task_line(before), "after": _task_line(after)})
    for key, label in (("title", "标题"), ("subject", "科目"), ("note", "备注")):
        if (before.get(key) or "") != (after.get(key) or ""):
            diff.append({"field": label, "before": before.get(key) or "无", "after": after.get(key) or "无"})
    if before["priority"] != after["priority"]:
        diff.append({"field": "优先级", "before": PRIORITY_LABELS.get(before["priority"], "无"),
                     "after": PRIORITY_LABELS.get(after["priority"], "无")})
    return diff


def _course_diff(before: dict, after: dict) -> List[dict]:
    diff = []
    if before["course_name"] != after["course_name"]:
        diff.append({"field": "课程名", "before": before["course_name"], "after": after["course_name"]})
    if _course_line(before) != _course_line(after):
        diff.append({"field": "时间", "before": _course_line(before), "after": _course_line(after)})
    if schedule.format_weeks(before["weeks"]) != schedule.format_weeks(after["weeks"]):
        diff.append({"field": "周次", "before": schedule.format_weeks(before["weeks"]),
                     "after": schedule.format_weeks(after["weeks"])})
    for key, label in (("classroom", "教室"), ("teacher", "老师")):
        if (before.get(key) or "") != (after.get(key) or ""):
            diff.append({"field": label, "before": before.get(key) or "无", "after": after.get(key) or "无"})
    return diff


# ---------------------------------------------------------------- 时间校验
class Checker:
    """
    校验任务时间 / 课程节次是否可用。提案生成时用来提前标黄提示，导入时作为最终校验。

    - 任务：已过去、跨午夜、与当天的课程重叠、与已有未完成任务重叠、与本次导入的其他条目重叠（硬错误）；
            不在偏好时段、占用饭点（只提示）。
    - 课程：星期 / 节次 / 周次越界、超出节次表、与已有课程或本次导入的其他课程冲突。
    """

    def __init__(self, db: Session, user: User, exclude_ids: Optional[Set[int]] = None):
        self.db, self.user = db, user
        self.exclude = set(exclude_ids or ())
        self.courses = schedule.user_courses(db, user)
        self.pref = prefs_service.effective(db, user)
        self.created: Set[int] = set()
        self._day_tasks: Dict[str, List[StudyTask]] = {}
        self.pending: List[Tuple[str, int, int, str]] = []  # 提案阶段尚未入库的条目
        self.pending_courses: List[dict] = []

    # ---- 任务
    def _tasks_on(self, day: str) -> List[StudyTask]:
        if day not in self._day_tasks:
            self._day_tasks[day] = visible_tasks(
                self.db.query(StudyTask).filter(
                    StudyTask.user_id == self.user.id, StudyTask.due_date == day,
                    StudyTask.start_time.isnot(None), StudyTask.completed.is_(False))
            ).all()
        return self._day_tasks[day]

    def include(self, task: StudyTask, created: bool = False) -> None:
        """应用成功后调用：让后面的条目能看到这条的新位置。"""
        self.exclude.discard(task.id)
        if created:
            self.created.add(task.id)
        self._day_tasks.clear()

    def task_issues(self, day: str, start: str, minutes: int) -> Tuple[List[str], List[str]]:
        """返回 (错误, 提示)。错误会导致导入失败。"""
        errors, warnings = [], []
        target = timeutil.parse_date(day)
        begin = timeutil.hm_to_minutes(start)
        end = begin + minutes
        today = timeutil.today()
        if target < today:
            errors.append(f"{_md(day)} 已经过去了")
        elif target == today and begin < timeutil.now().hour * 60 + timeutil.now().minute:
            errors.append(f"今天 {start} 已经过去了")
        if end > 24 * 60:
            errors.append("跨越午夜，请缩短时长或提前开始")
        for course in schedule.courses_on_date(self.db, self.user, target, self.courses):
            c1, c2 = timeutil.hm_to_minutes(course.start_time), timeutil.hm_to_minutes(course.end_time)
            if begin < c2 and c1 < end:
                errors.append(f"与课程「{course.course_name}」{course.start_time}-{course.end_time} 冲突")
        for task in self._tasks_on(day):
            if task.id in self.exclude or not task.end_time:
                continue
            t1 = task.start_time.hour * 60 + task.start_time.minute
            t2 = t1 + int(task.duration_minutes or 0)
            if begin < t2 and t1 < end:
                label = "本次导入的" if task.id in self.created else "已有任务"
                errors.append(f"与{label}「{task.title}」{task.start_time.strftime('%H:%M')}-"
                              f"{task.end_time.strftime('%H:%M')} 重叠")
        for p_day, p1, p2, title in self.pending:
            if p_day == day and begin < p2 and p1 < end:
                errors.append(f"与本次提案里的「{title}」{timeutil.minutes_to_hm(p1)}-{timeutil.minutes_to_hm(p2)} 重叠")
        earliest = timeutil.hm_to_minutes(self.pref.get("earliest") or "00:00")
        latest = timeutil.hm_to_minutes(self.pref.get("latest") or "23:59")
        if not errors and (begin < earliest or end > latest):
            warnings.append(f"不在你的学习时段 {self.pref.get('earliest')}-{self.pref.get('latest')} 内")
        for m1, m2, label in MEALS:
            if begin < timeutil.hm_to_minutes(m2) and timeutil.hm_to_minutes(m1) < end and not errors:
                warnings.append(f"占用了{label}时间")
        return errors[:3], warnings[:2]

    def hold(self, day: str, start: str, minutes: int, title: str) -> None:
        begin = timeutil.hm_to_minutes(start)
        self.pending.append((day, begin, begin + minutes, title))

    # ---- 课程
    def course_issues(self, data: dict, exclude_id: Optional[int] = None) -> List[str]:
        errors = []
        total = int(self.user.total_weeks or 20)
        periods = len(schedule.period_times(self.user))
        day, p1, p2 = data["day_of_week"], data["start_period"], data["end_period"]
        if not 1 <= day <= 7:
            errors.append("星期需在周一到周日之间")
        if p1 < 1 or p2 < p1:
            errors.append("节次不正确（结束节次不能早于开始节次）")
        elif p2 > periods:
            errors.append(f"超出节次表：当前节次表只有 {periods} 节")
        weeks = data["weeks"]
        if not weeks:
            errors.append("没有识别出上课周次")
        elif weeks[0] < 1 or weeks[-1] > total:
            errors.append(f"周次越界：本学期共 {total} 周")
        if errors:
            return errors
        for conflict in schedule.find_conflicts(self.courses, day, p1, p2, weeks, total, exclude_id=exclude_id):
            errors.append(f"与「{conflict['course_name']}」{conflict['periods']}在{conflict['overlap_weeks']}冲突")
        for other in self.pending_courses:
            if other["day_of_week"] == day and other["start_period"] <= p2 and p1 <= other["end_period"] \
                    and set(other["weeks"]) & set(weeks):
                errors.append(f"与本次提案里的「{other['course_name']}」冲突")
        return errors[:3]


# ---------------------------------------------------------------- 条目清洗
def clean_task(raw: dict) -> Tuple[Optional[dict], List[str]]:
    """把模型 / 前端提交的一条任务规范化；返回 (条目, 错误)。"""
    if not isinstance(raw, dict):
        return None, ["格式不正确"]
    errors = []
    day = str(raw.get("date") or raw.get("due_date") or "").strip()[:10]
    if not timeutil.parse_date(day):
        errors.append("日期格式应为 YYYY-MM-DD")
    start = raw.get("start_time")
    start = _hm(start) if start not in (None, "") else None
    if raw.get("start_time") not in (None, "") and start is None:
        errors.append("开始时间格式应为 HH:MM")
    minutes = _int(raw.get("duration_minutes"))
    if minutes is None or not 5 <= minutes <= 480:
        errors.append("时长需在 5-480 分钟之间")
    title = str(raw.get("title") or "").strip()[:200]
    if not title:
        errors.append("缺少标题")
    priority = _int(raw.get("priority"), 2)
    item = {
        "date": day, "start_time": start, "duration_minutes": minutes or 0, "title": title,
        "subject": str(raw.get("subject") or "").strip()[:80],
        "priority": max(0, min(3, priority if priority is not None else 2)),
        "note": str(raw.get("note") or "").strip()[:1000],
        "links": _clean_links(raw.get("links")),
    }
    return item, errors


def _weeks_of(user: User, raw: dict) -> List[int]:
    """优先用 weeks 列表；没有时解析 week_text；都没有表示整学期。周次越界保留，交给校验报错。"""
    total = int(user.total_weeks or 20)
    weeks = raw.get("weeks")
    if isinstance(weeks, list) and weeks:
        return sorted({w for w in (_int(x) for x in weeks) if w is not None})
    text = str(raw.get("week_text") or "").strip()
    if text:
        return schedule.parse_week_text(text, 60)
    return list(range(1, total + 1))


def clean_course(user: User, raw: dict) -> Tuple[Optional[dict], List[str]]:
    if not isinstance(raw, dict):
        return None, ["格式不正确"]
    name = str(raw.get("course_name") or raw.get("name") or "").strip()[:160]
    day, p1, p2 = _int(raw.get("day_of_week"), 0), _int(raw.get("start_period"), 0), _int(raw.get("end_period"), 0)
    errors = [] if name else ["缺少课程名"]
    weeks = _weeks_of(user, raw)
    item = {
        "course_name": name, "day_of_week": day, "start_period": p1, "end_period": p2,
        "weeks": weeks, "week_text": schedule.format_weeks(weeks),
        "classroom": str(raw.get("classroom") or "").strip()[:80],
        "teacher": str(raw.get("teacher") or "").strip()[:120],
        "note": str(raw.get("note") or "").strip()[:200],
        "start_time": None, "end_time": None,
    }
    periods = len(schedule.period_times(user))
    if 1 <= p1 <= p2 <= periods:
        item["start_time"], item["end_time"] = schedule.periods_to_times(user, p1, p2)
    return item, errors


# ---------------------------------------------------------------- 提案（生成时校验，标黄提示）
def build_task_proposal(db: Session, user: User, raw_items, title: str = "", summary: str = "") -> Tuple[dict, dict]:
    """返回 (提案, 给模型看的工具结果)。"""
    checker = Checker(db, user)
    items, issues, dropped = [], [], 0
    for raw in (raw_items if isinstance(raw_items, list) else [])[:MAX_ITEMS]:
        item, errors = clean_task(raw)
        if item is None or not item["title"] or not timeutil.parse_date(item["date"]) or not item["duration_minutes"]:
            dropped += 1
            continue
        warnings = list(errors)
        blocking = list(errors)
        if item["start_time"] and not errors:
            hard, soft = checker.task_issues(item["date"], item["start_time"], item["duration_minutes"])
            blocking += hard
            warnings += hard + soft
            if not hard:
                checker.hold(item["date"], item["start_time"], item["duration_minutes"], item["title"])
        item["warnings"] = warnings
        if blocking:
            issues.append(f"{_md(item['date'])} {item['start_time'] or ''}「{item['title']}」：{'；'.join(blocking)}")
        items.append(item)
    items.sort(key=lambda t: (t["date"], t["start_time"] or "99:99"))
    for index, item in enumerate(items):
        item["key"] = f"t{index}"
    dates = sorted({t["date"] for t in items})
    proposal = {
        "id": _short_id(), "type": "tasks",
        "title": (title or "").strip()[:40] or "AI 学习安排",
        "summary": (summary or "").strip()[:300],
        "items": items, "results": {}, "applied": False, "plan_id": None,
    }
    result = {
        "ok": bool(items), "proposal_id": proposal["id"], "count": len(items),
        "total_minutes": sum(t["duration_minutes"] for t in items),
        "dates": dates, "issues": issues[:10],
        "note": "提案卡片已展示给同学，等待确认导入。" + (f"{dropped} 条缺少日期 / 标题 / 时长，已丢弃。" if dropped else ""),
    }
    return proposal, result


def build_course_proposal(db: Session, user: User, raw_items) -> Tuple[dict, dict]:
    checker = Checker(db, user)
    items, issues = [], []
    for raw in (raw_items if isinstance(raw_items, list) else [])[:40]:
        item, errors = clean_course(user, raw)
        if item is None or not item["course_name"]:
            continue
        errors += checker.course_issues(item)
        if not errors:
            checker.pending_courses.append(item)
        item["warnings"] = errors
        if errors:
            issues.append(f"「{item['course_name']}」：{'；'.join(errors)}")
        items.append(item)
    for index, item in enumerate(items):
        item["key"] = f"c{index}"
    proposal = {"id": _short_id(), "type": "courses", "title": "新增课程", "items": items,
                "results": {}, "applied": False,
                "period_count": len(schedule.period_times(user)), "total_weeks": int(user.total_weeks or 20)}
    result = {"ok": bool(items), "proposal_id": proposal["id"], "count": len(items), "issues": issues,
              "note": "课程提案卡片已展示给同学，等待确认导入。"}
    return proposal, result


def _merge_task(snap: dict, changes: dict) -> dict:
    merged = dict(snap)
    for key in ("title", "subject", "note", "priority", "duration_minutes"):
        if key in changes and changes[key] is not None:
            merged[key] = changes[key]
    if changes.get("date") or changes.get("due_date"):
        merged["date"] = changes.get("date") or changes.get("due_date")
    if "start_time" in changes:
        merged["start_time"] = changes["start_time"]
    return merged


def _merge_course(snap: dict, changes: dict) -> dict:
    merged = dict(snap)
    for key in ("course_name", "day_of_week", "start_period", "end_period", "classroom", "teacher", "note"):
        if key in changes and changes[key] is not None:
            merged[key] = changes[key]
    if changes.get("weeks"):
        merged["weeks"], merged["week_text"] = changes["weeks"], None
    elif changes.get("week_text"):
        merged["weeks"], merged["week_text"] = None, changes["week_text"]
    return merged


def _describe_change(db: Session, user: User, raw: dict, checker: Checker) -> Tuple[Optional[dict], List[str]]:
    """把一条修改规范化：查出真实对象、算出修改前→修改后。找不到对象返回 (None, [原因])。"""
    if not isinstance(raw, dict):
        return None, ["格式不正确"]
    target = raw.get("target") if raw.get("target") in ("task", "course") else "task"
    action = "delete" if raw.get("action") == "delete" else "update"
    obj_id = _int(raw.get("id"))
    changes = raw.get("changes") if isinstance(raw.get("changes"), dict) else {}
    item = {"target": target, "action": action, "id": obj_id, "changes": changes,
            "reason": str(raw.get("reason") or "").strip()[:200], "warnings": []}
    if target == "task":
        task = db.query(StudyTask).filter(StudyTask.id == obj_id, StudyTask.user_id == user.id).first() \
            if obj_id else None
        if task is None:
            return None, [f"任务 id={obj_id} 不存在（请先用 list_tasks 查真实 id）"]
        before = _task_snapshot(task)
        item.update(title=task.title, before=before)
        if action == "delete":
            item.update(after=None, diff=[], summary=f"删除任务「{task.title}」（{_task_line(before)}）")
            return item, []
        after, errors = clean_task(_merge_task(before, changes))
        after.pop("links", None)
        item.update(after=after, diff=_task_diff(before, after))
        if not errors and after["start_time"] and (after["date"], after["start_time"], after["duration_minutes"]) != \
                (before["date"], before["start_time"], before["duration_minutes"]):
            hard, soft = checker.task_issues(after["date"], after["start_time"], after["duration_minutes"])
            errors += hard
            item["warnings"] += soft
            if not hard:
                checker.hold(after["date"], after["start_time"], after["duration_minutes"], after["title"])
        item["warnings"] = errors + item["warnings"]
        item["summary"] = "；".join(f"{d['field']}：{d['before']} → {d['after']}" for d in item["diff"]) or "没有变化"
        return item, []
    course = db.query(Timetable).filter(Timetable.id == obj_id, Timetable.user_id == user.id).first() if obj_id else None
    if course is None:
        return None, [f"课程 id={obj_id} 不存在（请先用 list_courses 查真实 id）"]
    before = _course_snapshot(user, course)
    item.update(title=course.course_name, before=before)
    if action == "delete":
        item.update(after=None, diff=[], summary=f"从课表删除「{course.course_name}」（{_course_line(before)} {before['week_text']}）")
        return item, []
    after, errors = clean_course(user, _merge_course(before, changes))
    if not errors:
        errors += checker.course_issues(after, exclude_id=course.id)
    item.update(after=after, diff=_course_diff(before, after), warnings=errors)
    item["summary"] = "；".join(f"{d['field']}：{d['before']} → {d['after']}" for d in item["diff"]) or "没有变化"
    return item, []


def build_change_proposal(db: Session, user: User, raw_items, summary: str = "") -> Tuple[dict, dict]:
    raw_list = (raw_items if isinstance(raw_items, list) else [])[:MAX_ITEMS]
    task_ids = {_int(r.get("id")) for r in raw_list if isinstance(r, dict) and r.get("target", "task") == "task"}
    checker = Checker(db, user, exclude_ids={i for i in task_ids if i})
    items, invalid, issues = [], [], []
    for raw in raw_list:
        item, problems = _describe_change(db, user, raw, checker)
        if item is None:
            invalid += problems
            continue
        if item["warnings"]:
            issues.append(f"「{item['title']}」：{'；'.join(item['warnings'])}")
        items.append(item)
    for index, item in enumerate(items):
        item["key"] = f"m{index}"
    proposal = {"id": _short_id(), "type": "changes", "title": "修改已有内容", "summary": (summary or "").strip()[:300],
                "items": items, "results": {}, "applied": False}
    result = {"ok": bool(items), "proposal_id": proposal["id"] if items else None, "count": len(items),
              "items": [f"{i['title']}：{i['summary']}" for i in items][:20],
              "invalid": invalid[:10], "issues": issues[:10],
              "note": "修改提案已展示给同学，等待确认。" if items else "没有可用的修改，请先查询真实 id。"}
    return proposal, result


def build_ask(question: str, options) -> dict:
    opts = [str(o).strip()[:30] for o in (options if isinstance(options, list) else []) if str(o).strip()][:4]
    return {"id": _short_id(), "type": "ask", "question": str(question or "").strip()[:300] or "能再具体说说吗？",
            "options": opts, "answered": False}


# ---------------------------------------------------------------- 应用提案（逐条校验、逐条应用）
def _fail(key, title, reason: str) -> dict:
    return {"key": key, "ok": False, "title": title, "reason": reason}


def _apply_tasks(db: Session, user: User, items: List[dict], title: Optional[str], goal: Optional[str],
                 plan_id: Optional[int]) -> dict:
    plan = None
    if plan_id:
        plan = get_owned_plan(db, user, plan_id)
        if plan.deleted_at is not None:
            plan = None
    checker = Checker(db, user)
    results, created = [], []
    for raw in items:
        key = raw.get("key") if isinstance(raw, dict) else None
        item, errors = clean_task(raw)
        label = (item or {}).get("title") or "未命名任务"
        if not errors and item["start_time"]:
            errors, _ = checker.task_issues(item["date"], item["start_time"], item["duration_minutes"])
        elif not errors and timeutil.parse_date(item["date"]) < timeutil.today():
            errors = [f"{_md(item['date'])} 已经过去了"]
        if errors:
            results.append(_fail(key, label, "；".join(errors)))
            continue
        if plan is None:
            plan = StudyPlan(user_id=user.id, title=(title or "AI 学习安排")[:200], goal=goal, status="active",
                             source="ai", start_date=item["date"], end_date=item["date"], duration_days=1,
                             content=json.dumps({"provider": "agent"}, ensure_ascii=False))
            db.add(plan)
            db.flush()
        # 学习资源链接统一写进备注（用户要求），任务详情里点链接即可打开
        task = StudyTask(user_id=user.id, plan_id=plan.id, title=item["title"], subject=item["subject"] or None,
                         note=_note_with_links(item["note"], item["links"]), priority=item["priority"],
                         source="ai", status="todo")
        try:
            apply_schedule(task, item["date"], item["start_time"], item["duration_minutes"])
        except ApiError as error:
            results.append(_fail(key, label, error.message))
            continue
        db.add(task)
        db.flush()
        checker.include(task, created=True)
        created.append(task)
        results.append({"key": key, "ok": True, "title": task.title, "id": task.id,
                        "summary": _task_line(_task_snapshot(task))})
    if plan is not None and created:
        db.refresh(plan)
        days = sorted({t.due_date for t in plan.tasks if t.due_date})
        plan.start_date, plan.end_date = days[0], days[-1]
        plan.duration_days = (timeutil.parse_date(days[-1]) - timeutil.parse_date(days[0])).days + 1
        plan.available_hours = round(sum(int(t.duration_minutes or 0) for t in plan.tasks) / 60)
        db.flush()
    return {"results": results, "plan": plan if created else None}


def _course_payload(item: dict) -> dict:
    return {k: item[k] for k in ("course_name", "day_of_week", "start_period", "end_period", "weeks",
                                 "classroom", "teacher", "note")}


def _course_summary(user: User, course: Timetable) -> str:
    data = schedule.course_to_dict(course, int(user.total_weeks or 20))
    return f"{WEEK_CN[course.day_of_week]} {course.start_period}-{course.end_period}节 " \
           f"{data['start_time']}-{data['end_time']} · {data['week_text']}"


def _apply_courses(db: Session, user: User, items: List[dict]) -> dict:
    checker = Checker(db, user)
    results = []
    for raw in items:
        key = raw.get("key") if isinstance(raw, dict) else None
        item, errors = clean_course(user, raw)
        label = (item or {}).get("course_name") or "未命名课程"
        if not errors:
            errors = checker.course_issues(item)
        if errors:
            results.append(_fail(key, label, "；".join(errors)))
            continue
        try:
            course = schedule.save_course(db, user, _course_payload(item))
        except ApiError as error:
            results.append(_fail(key, label, error.message))
            continue
        checker.courses.append(course)
        results.append({"key": key, "ok": True, "title": course.course_name, "id": course.id,
                        "summary": _course_summary(user, course)})
    return {"results": results, "plan": None}


def _change_task(db: Session, user: User, raw: dict, checker: Checker) -> dict:
    key, obj_id = raw.get("key"), _int(raw.get("id"))
    changes = raw.get("changes") if isinstance(raw.get("changes"), dict) else {}
    # 归属校验：只能改自己的任务
    task = db.query(StudyTask).filter(StudyTask.id == obj_id, StudyTask.user_id == user.id).first() if obj_id else None
    if task is None:
        return _fail(key, raw.get("title") or "任务", "任务不存在或已被删除")
    if raw.get("action") == "delete":
        db.query(FocusRecord).filter(FocusRecord.task_id == task.id).update({"task_id": None})
        db.query(StudyTask).filter(StudyTask.repeat_parent_id == task.id).update({"repeat_parent_id": None})
        title = task.title
        db.delete(task)
        db.flush()
        checker.exclude.discard(obj_id)
        checker._day_tasks.clear()
        return {"key": key, "ok": True, "title": title, "id": obj_id, "summary": "已删除"}
    before = _task_snapshot(task)
    after, errors = clean_task(_merge_task(before, changes))
    moved = (after["date"], after["start_time"], after["duration_minutes"]) != \
        (before["date"], before["start_time"], before["duration_minutes"])
    if not errors and moved and after["start_time"]:
        errors, _ = checker.task_issues(after["date"], after["start_time"], after["duration_minutes"])
    elif not errors and moved and timeutil.parse_date(after["date"]) < timeutil.today():
        errors = [f"{_md(after['date'])} 已经过去了"]
    if errors:
        return _fail(key, task.title, "；".join(errors))
    if after["start_time"] and timeutil.hm_to_minutes(after["start_time"]) + after["duration_minutes"] > 24 * 60:
        return _fail(key, task.title, "跨越午夜，请缩短时长或提前开始")
    task.title, task.subject, task.note = after["title"], after["subject"] or None, after["note"] or None
    task.priority = after["priority"]
    apply_schedule(task, after["date"], after["start_time"], after["duration_minutes"])
    db.flush()
    checker.include(task)
    diff = _task_diff(before, _task_snapshot(task))
    return {"key": key, "ok": True, "title": task.title, "id": task.id,
            "summary": "；".join(f"{d['field']}：{d['before']} → {d['after']}" for d in diff) or "没有变化"}


def _change_course(db: Session, user: User, raw: dict, checker: Checker) -> dict:
    key, obj_id = raw.get("key"), _int(raw.get("id"))
    changes = raw.get("changes") if isinstance(raw.get("changes"), dict) else {}
    course = db.query(Timetable).filter(Timetable.id == obj_id, Timetable.user_id == user.id).first() if obj_id else None
    if course is None:
        return _fail(key, raw.get("title") or "课程", "课程不存在或已被删除")
    if raw.get("action") == "delete":
        name = course.course_name
        checker.courses = [c for c in checker.courses if c.id != course.id]
        db.delete(course)
        db.flush()
        return {"key": key, "ok": True, "title": name, "id": obj_id, "summary": "已从课表删除"}
    before = _course_snapshot(user, course)
    after, errors = clean_course(user, _merge_course(before, changes))
    if not errors:
        errors = checker.course_issues(after, exclude_id=course.id)
    if errors:
        return _fail(key, course.course_name, "；".join(errors))
    try:
        schedule.save_course(db, user, {**_course_payload(after), "color": course.color}, course=course)
    except ApiError as error:
        return _fail(key, course.course_name, error.message)
    diff = _course_diff(before, _course_snapshot(user, course))
    return {"key": key, "ok": True, "title": course.course_name, "id": course.id,
            "summary": "；".join(f"{d['field']}：{d['before']} → {d['after']}" for d in diff) or "没有变化"}


def _apply_changes(db: Session, user: User, items: List[dict]) -> dict:
    task_ids = {_int(r.get("id")) for r in items if isinstance(r, dict) and r.get("target", "task") == "task"}
    checker = Checker(db, user, exclude_ids={i for i in task_ids if i})
    results = []
    for raw in items:
        if not isinstance(raw, dict):
            results.append(_fail(None, "未知条目", "格式不正确"))
        elif raw.get("target") == "course":
            results.append(_change_course(db, user, raw, checker))
        else:
            results.append(_change_task(db, user, raw, checker))
    return {"results": results, "plan": None}


def apply_proposal(db: Session, user: User, kind: str, items: List[dict], title: Optional[str] = None,
                   goal: Optional[str] = None, plan_id: Optional[int] = None) -> dict:
    """返回 {"results": [{key, ok, title, id?, summary?, reason?}], "plan": StudyPlan|None}。不提交事务。"""
    if kind == "tasks":
        return _apply_tasks(db, user, items, title, goal, plan_id)
    if kind == "courses":
        return _apply_courses(db, user, items)
    return _apply_changes(db, user, items)


# ---------------------------------------------------------------- 消息 meta 与历史
def load_meta(message: ChatMessage) -> dict:
    try:
        value = json.loads(message.meta) if message.meta else {}
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


EDITABLE_FIELDS = ("date", "start_time", "duration_minutes", "day_of_week", "start_period", "end_period",
                   "classroom", "week_text", "weeks", "end_time")


def record_results(db: Session, user: User, message_id: Optional[int], proposal_id: Optional[str],
                   items: List[dict], results: List[dict], plan_id: Optional[int]) -> None:
    """把导入结果写回消息的 meta：刷新页面后卡片仍显示每条成功 / 失败，也保留用户在卡片上的编辑。"""
    if not message_id or not proposal_id:
        return
    message = db.query(ChatMessage).filter(ChatMessage.id == message_id, ChatMessage.user_id == user.id).first()
    if message is None:
        return
    meta = load_meta(message)
    for proposal in meta.get("proposals") or []:
        if proposal.get("id") != proposal_id:
            continue
        edited = {i.get("key"): i for i in items if isinstance(i, dict) and i.get("key")}
        if proposal.get("type") in ("tasks", "courses"):
            for stored in proposal.get("items") or []:
                change = edited.get(stored.get("key"))
                for field in EDITABLE_FIELDS:
                    if change and field in change:
                        stored[field] = change[field]
        stored_results = proposal.setdefault("results", {})
        for result in results:
            if result.get("key"):
                stored_results[result["key"]] = result
        proposal["applied"] = True
        if plan_id:
            proposal["plan_id"] = plan_id
    message.meta = json.dumps(meta, ensure_ascii=False)


def _proposal_note(proposal: dict) -> str:
    """把提案压缩成给模型看的一段文字，后续追问时模型才知道自己提过什么、同学导入了哪些。"""
    kind = proposal.get("type")
    results = proposal.get("results") or {}
    done = sum(1 for r in results.values() if r.get("ok"))
    failed = sum(1 for r in results.values() if not r.get("ok"))
    if proposal.get("applied"):
        status = f"（已导入 {done} 条" + (f"，失败 {failed} 条" if failed else "") + "）"
    else:
        status = "（尚未导入）"
    items = proposal.get("items") or []
    if kind == "ask":
        options = "、".join(proposal.get("options") or [])
        return f"[追问] {proposal.get('question')}" + (f"（选项：{options}）" if options else "")
    if kind == "tasks":
        lines = [f"{_task_line(t)} {t.get('title')}" for t in items[:12]]
        return f"[任务提案「{proposal.get('title')}」{len(items)} 条{status}] " + "；".join(lines)
    if kind == "courses":
        lines = [f"{c.get('course_name')} {c.get('start_period')}-{c.get('end_period')}节 {c.get('week_text')}"
                 for c in items[:10]]
        return f"[课程提案 {len(items)} 门{status}] " + "；".join(lines)
    lines = [f"{c.get('title')}：{c.get('summary')}" for c in items[:12]]
    return f"[修改提案 {len(items)} 条{status}] " + "；".join(lines)


def history_messages(db: Session, conversation_id: int, user: User, limit: int = HISTORY_LIMIT) -> List[dict]:
    rows = (db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation_id, ChatMessage.user_id == user.id)
            .order_by(ChatMessage.id.desc()).limit(limit).all())
    messages = []
    for row in reversed(rows):
        content = row.content or ""
        if row.role == "assistant":
            notes = [_proposal_note(p) for p in load_meta(row).get("proposals") or []]
            content = "\n".join([content] + notes).strip()
        if content:
            messages.append({"role": "user" if row.role == "user" else "assistant", "content": content[:3000]})
    return messages


# ---------------------------------------------------------------- 读工具
def tool_get_context(db: Session, user: User, _args: dict) -> dict:
    now = timeutil.now()
    today = now.date()
    pref = prefs_service.effective(db, user)
    exams = (db.query(Exam).filter(Exam.user_id == user.id, Exam.exam_date >= today.isoformat())
             .order_by(Exam.exam_date).limit(10).all())
    week = schedule.teaching_week(user, today)
    monday = timeutil.monday_of(today)
    return {
        "today": today.isoformat(), "weekday": timeutil.weekday_label(today), "now": now.strftime("%H:%M"),
        "timezone": "Asia/Shanghai",
        "this_week": [monday.isoformat(), (monday + timedelta(days=6)).isoformat()],
        "teaching_week": week,
        "teaching_week_note": "未设置开学日期" if week is None else ("学期外" if week == 0 else ""),
        "total_weeks": int(user.total_weeks or 20),
        "period_times": [f"第{i + 1}节 {p['start']}-{p['end']}" for i, p in enumerate(schedule.period_times(user))],
        "study_prefs": {**pref, "text": prefs_service.describe(pref)},
        "daily_goal_minutes": int(user.daily_goal_minutes or 60),
        "exams": [{"title": e.title, "subject": e.subject or "", "date": e.exam_date, "start_time": e.start_time or "",
                   "days_left": (date.fromisoformat(e.exam_date) - today).days} for e in exams],
    }


def tool_list_courses(db: Session, user: User, _args: dict) -> dict:
    courses = schedule.user_courses(db, user)
    total = int(user.total_weeks or 20)
    return {"semester": schedule.effective_semester(db, user), "count": len(courses), "courses": [
        {"id": c.id, "name": c.course_name, "weekday": WEEK_CN[c.day_of_week] if 1 <= c.day_of_week <= 7 else "?",
         "day_of_week": c.day_of_week, "periods": f"{c.start_period}-{c.end_period}",
         "time": f"{c.start_time}-{c.end_time}",
         "weeks": c.week_text or schedule.format_weeks(schedule.course_weeks(c, total)),
         "classroom": c.classroom or "", "teacher": c.teacher or ""} for c in courses]}


def _range(args: dict, max_days: int) -> Tuple[date, date]:
    today = timeutil.today()
    start = timeutil.parse_date(args.get("start"), today)
    end = timeutil.parse_date(args.get("end"), start + timedelta(days=6))
    if end < start:
        start, end = end, start
    return start, min(end, start + timedelta(days=max_days - 1))


def tool_list_tasks(db: Session, user: User, args: dict) -> dict:
    start, end = _range(args, 62)
    query = visible_tasks(db.query(StudyTask).filter(
        StudyTask.user_id == user.id, StudyTask.due_date >= start.isoformat(), StudyTask.due_date <= end.isoformat()))
    if not args.get("include_completed"):
        query = query.filter(StudyTask.completed.is_(False))
    keyword = str(args.get("query") or "").strip().replace("%", "").replace("_", "")[:40]
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(StudyTask.title.ilike(like) | StudyTask.subject.ilike(like) | StudyTask.note.ilike(like))
    far = timeutil.combine(start, "23:59")
    tasks = sorted(query.all(), key=lambda t: (t.due_date or "", t.start_time or far))[:80]
    return {"range": [start.isoformat(), end.isoformat()], "count": len(tasks), "tasks": [
        {"id": t.id, "title": t.title, "subject": t.subject or "", "date": t.due_date,
         "start_time": t.start_time.strftime("%H:%M") if t.start_time else None,
         "end_time": t.end_time.strftime("%H:%M") if t.end_time else None,
         "duration_minutes": int(t.duration_minutes or 0), "priority": int(t.priority or 0),
         "completed": bool(t.completed), "plan": t.plan.title if t.plan_id and t.plan else None} for t in tasks]}


def tool_free_slots(db: Session, user: User, args: dict) -> dict:
    start, end = _range(args, 14)
    days = (end - start).days + 1
    pref = prefs_service.effective(db, user)
    contexts = planner.day_contexts(db, user, start, days, None, pref)
    timed = visible_tasks(db.query(StudyTask).filter(
        StudyTask.user_id == user.id, StudyTask.start_time.isnot(None), StudyTask.completed.is_(False),
        StudyTask.due_date >= start.isoformat(), StudyTask.due_date <= end.isoformat())).all()
    timed.sort(key=lambda t: t.start_time)
    out = []
    for ctx in contexts:
        key = ctx["date"].isoformat()
        out.append({
            "date": key, "weekday": timeutil.weekday_label(ctx["date"]),
            "courses": [f"{c['start']}-{c['end']} {c['name']}" for c in ctx["courses"]],
            "tasks": [f"{t.start_time.strftime('%H:%M')}-{t.end_time.strftime('%H:%M')} {t.title}"
                      for t in timed if t.due_date == key and t.end_time],
            "free": [f"{s['start']}-{s['end']}" for s in sorted(ctx["free"], key=lambda s: s["start"])],
            "free_minutes": sum(s["minutes"] for s in ctx["free"]),
        })
    return {"prefs": prefs_service.describe(pref), "days": out,
            "note": "free 已扣掉课程前后 10 分钟、已有任务、饭点和偏好以外的时间"}


READ_TOOLS = {"get_context": tool_get_context, "list_courses": tool_list_courses,
              "list_tasks": tool_list_tasks, "get_free_slots": tool_free_slots}


def _tool_summary(name: str, result: dict) -> str:
    if not isinstance(result, dict):
        return ""
    if result.get("error"):
        return f"失败：{str(result['error'])[:60]}"
    if name == "get_context":
        week = result.get("teaching_week")
        return f"{result.get('today')} {result.get('weekday')}" + (f" · 第 {week} 周" if week else "")
    if name == "list_courses":
        return f"{result.get('count', 0)} 门课程"
    if name == "list_tasks":
        return f"{result.get('count', 0)} 个任务"
    if name == "get_free_slots":
        minutes = sum(d.get("free_minutes", 0) for d in result.get("days") or [])
        return f"{len(result.get('days') or [])} 天，共 {minutes // 60} 小时 {minutes % 60} 分空闲"
    if name.startswith("propose_"):
        return f"{result.get('count', 0)} 条" + (f"，{len(result['issues'])} 条有问题" if result.get("issues") else "")
    if isinstance(result.get("results"), list):
        return f"找到 {len(result['results'])} 条结果"
    return ""


# ---------------------------------------------------------------- 一轮对话
class TurnState:
    """一轮对话的累计结果；客户端中途断开时路由据此保存已生成的部分。"""

    def __init__(self):
        self.content = ""
        self.reasoning = ""
        self.tools: List[dict] = []
        self.proposals: List[dict] = []
        self.engine = "rule"
        self.model = "本地规则引擎"
        self.notice = ""
        self.error = ""
        self.usage: Dict[str, int] = {}
        self.memory: Optional[dict] = None

    def meta(self) -> dict:
        data = {"engine": self.engine, "model": self.model, "tools": self.tools[:20], "proposals": self.proposals}
        if self.reasoning:
            data["reasoning"] = self.reasoning[:REASONING_KEEP]
            data["reasoning_chars"] = len(self.reasoning)
        if self.notice:
            data["notice"] = self.notice
        if self.error:
            data["error"] = self.error
        if self.usage:
            data["usage"] = self.usage
        return data


def _event(event: str, **data) -> dict:
    return {"event": event, "data": data}


def _add_proposal(state: TurnState, proposal: dict) -> Optional[str]:
    """同一轮里同类提案（任务 / 课程 / 修改）再次生成时替换上一张，避免重复卡片。返回被替换的 id。"""
    if proposal["type"] == "ask":
        state.proposals.append(proposal)
        return None
    for index, old in enumerate(state.proposals):
        if old["type"] == proposal["type"]:
            state.proposals[index] = proposal
            return old["id"]
    state.proposals.append(proposal)
    return None


def execute_tool(db: Session, user: User, name: str, args: dict) -> Tuple[dict, Optional[dict], bool]:
    """执行一个工具，返回 (给模型的结果, 产生的提案, 是否结束本轮)。工具内部异常转成 error，不中断对话。"""
    try:
        if name in READ_TOOLS:
            return READ_TOOLS[name](db, user, args), None, False
        if name == "propose_tasks":
            proposal, result = build_task_proposal(db, user, args.get("items"), args.get("title") or "",
                                                   args.get("summary") or "")
            return result, proposal if proposal["items"] else None, False
        if name == "propose_courses":
            proposal, result = build_course_proposal(db, user, args.get("items"))
            return result, proposal if proposal["items"] else None, False
        if name == "propose_changes":
            proposal, result = build_change_proposal(db, user, args.get("items"), args.get("summary") or "")
            return result, proposal if proposal["items"] else None, False
        if name == "ask_user":
            proposal = build_ask(args.get("question"), args.get("options"))
            return {"ok": True, "note": "问题已展示给同学，本轮结束，等待回答。"}, proposal, True
        if search_tools is not None and name in {t.get("function", {}).get("name") for t in _search_tools()}:
            result = search_tools.run(name, args, user=user, db=db)
            return (result if isinstance(result, dict) else {"result": result}), None, False
        return {"error": f"没有这个工具：{name}"}, None, False
    except Exception as error:  # noqa: BLE001 - 单个工具出错不应让整轮对话失败
        logger.exception("工具 %s 执行失败", name)
        return {"error": f"工具执行出错：{str(error)[:120]}"}, None, False


def _relay(stream, state: TurnState) -> Iterator[dict]:
    """把 llm.stream_chat 的片段转成 SSE 事件，同时累计到 state；返回 StreamResult。"""
    first_text = True
    try:
        while True:
            try:
                kind, piece = next(stream)
            except StopIteration as stop:
                return stop.value
            if kind == "reasoning":
                state.reasoning += piece
                yield _event("reasoning", delta=piece)
            else:
                if first_text and state.content and not state.content.endswith("\n"):
                    state.content += "\n\n"
                    yield _event("text", delta="\n\n")
                first_text = False
                state.content += piece
                yield _event("text", delta=piece)
    finally:
        stream.close()


def run_turn(db: Session, user: User, conversation_id: int, state: TurnState) -> Iterator[dict]:
    """
    处理一条用户消息（已存入 ChatMessage）。逐个产出事件：status / reasoning / text / tool / proposal。
    结束后结果在 state 里，由调用方保存助手消息并发送 done。
    """
    config = providers.resolve(db, user)
    history = history_messages(db, conversation_id, user)
    if config is None:
        yield from _rule_turn(db, user, history, state)
        return
    state.engine, state.model = "agent", f"{config.name} · {config.model}"
    yield _event("status", text="正在思考…" if llm.supports_thinking(config) else "正在理解你的需求…")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    tools = tool_definitions()
    for step in range(MAX_STEPS + 1):
        final = step == MAX_STEPS
        if final:
            messages.append({"role": "user", "content": "（系统提示：工具调用次数已用完，请根据已有信息直接给出最终回复，不要再调用工具。）"})
        before_content = state.content
        try:
            try:
                result = yield from _relay(llm.stream_chat(config, messages, tools=tools), state)
            except llm.LlmError as error:
                # 网络抖动（连接重置、超时、5xx）重试一次本步；参数错误等 4xx 不重试
                if error.status is not None and error.status < 500:
                    raise
                logger.warning("模型调用中断，重试本步：%s", error.message)
                if state.content != before_content:
                    state.content = before_content
                    yield _event("text", delta="", replace=state.content)
                yield _event("status", text="连接不稳定，正在重试…")
                result = yield from _relay(llm.stream_chat(config, messages, tools=tools), state)
        except llm.LlmError as error:
            if step == 0 and llm.tools_unsupported(error):
                logger.info("模型不支持工具调用，降级为 JSON 草稿：%s", error.detail or error.message)
                yield from _draft_turn(db, user, history, state, config, "当前模型不支持工具调用，已切换为简化规划模式")
                return
            if step == 0 and not state.content:
                logger.warning("智能体调用失败，回退规则引擎：%s", error.message)
                state.notice = f"模型调用失败（{error.message}），本次由本地规则引擎生成"
                yield from _rule_turn(db, user, history, state, keep_engine=False)
                return
            state.error = error.message
            yield _event("error", message=f"模型调用中断：{error.message}")
            return
        for key, value in (result.usage or {}).items():
            if isinstance(value, int):
                state.usage[key] = state.usage.get(key, 0) + value
        calls = result.tool_calls or []
        if not calls or final:
            break
        # 调工具前顺手写的话（"我来查一下…"）不算最终回复：移到思考过程里，避免正文前后重复；
        # 追问时保留，那段话就是给同学的说明
        asking = any(c["function"]["name"] == "ask_user" for c in calls)
        if not asking and state.content != before_content:
            interim = state.content[len(before_content):].strip()
            state.content = before_content
            if interim:
                state.reasoning += f"\n【过程】{interim}\n"
                yield _event("reasoning", delta=f"\n【过程】{interim}\n")
            yield _event("text", delta="", replace=state.content)
        # 带工具调用的助手回合：按 DeepSeek 要求原样回传 reasoning_content
        assistant = {"role": "assistant", "content": result.content or "", "tool_calls": calls}
        if result.reasoning:
            assistant["reasoning_content"] = result.reasoning
        messages.append(assistant)
        halt = False
        for call in calls:
            name = call["function"]["name"]
            label = TOOL_LABELS.get(name) or ("联网搜索" if "search" in name else name)
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
                args = args if isinstance(args, dict) else {}
            except ValueError:
                args = None
            yield _event("tool", id=call["id"], name=name, label=label, status="running")
            if args is None:
                output, proposal, stop = {"error": "参数不是合法的 JSON，请重新调用"}, None, False
            else:
                output, proposal, stop = execute_tool(db, user, name, args)
            summary = _tool_summary(name, output)
            state.tools.append({"name": name, "label": label, "summary": summary})
            yield _event("tool", id=call["id"], name=name, label=label, status="done", summary=summary)
            if proposal is not None:
                replaced = _add_proposal(state, proposal)
                yield _event("proposal", proposal=proposal, replaces=replaced)
            halt = halt or stop
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(output, ensure_ascii=False, default=str)[:8000]})
        if halt:
            break
    if not state.content.strip() and not state.proposals:
        state.content = "我没能得出结论，可以换个说法再试一次吗？"
        yield _event("text", delta=state.content)


# ---------------------------------------------------------------- 降级：JSON 草稿 / 规则引擎
def _draft_proposals(state: TurnState, draft: dict) -> Iterator[dict]:
    if draft.get("tasks"):
        proposal = {"id": _short_id(), "type": "tasks", "title": draft.get("title") or "AI 学习安排",
                    "summary": draft.get("reply") or "", "items": [], "results": {}, "applied": False, "plan_id": None}
        for index, task in enumerate(draft["tasks"]):
            proposal["items"].append({**task, "links": [], "warnings": [], "key": f"t{index}"})
        state.proposals.append(proposal)
        yield _event("proposal", proposal=proposal, replaces=None)
    if draft.get("courses"):
        proposal = {"id": _short_id(), "type": "courses", "title": "新增课程", "items": [], "results": {},
                    "applied": False}
        for index, course in enumerate(draft["courses"]):
            proposal["items"].append({**course, "warnings": [], "key": f"c{index}"})
        state.proposals.append(proposal)
        yield _event("proposal", proposal=proposal, replaces=None)


def _last_user(history: List[dict]) -> str:
    for turn in reversed(history):
        if turn["role"] == "user":
            return turn["content"]
    return ""


def _draft_turn(db: Session, user: User, history: List[dict], state: TurnState, config, notice: str) -> Iterator[dict]:
    state.engine = "draft"
    state.notice = notice
    yield _event("status", text="正在生成计划…")
    message = _last_user(history)
    try:
        draft = planner.generate_draft(db, user, message[:500], use_ai=True,
                                       history=[{"role": t["role"], "content": t["content"][:1500]} for t in history[:-1]],
                                       memory=state.memory)
    except ApiError as error:
        state.content = error.message
        yield _event("text", delta=state.content)
        return
    state.model = draft.get("model") or state.model
    state.memory = draft.get("memory")
    state.content = (draft.get("advice") or draft.get("reply") or "").strip()
    if draft.get("fallback_reason"):
        state.notice = f"{notice}；模型未能生成（{draft['fallback_reason']}），本次由规则引擎完成"
    yield _event("text", delta=state.content)
    yield from _draft_proposals(state, draft)


COURSE_INTENT = re.compile(r"(\d+\s*[-到至~]\s*\d+\s*节|第?\s*\d+\s*节课|选修|必修|课表里?加|加(一|门)?(节|门)?课|新增课程|添加课程|周次)")
CHANGE_INTENT = re.compile(r"(挪|推迟|延后|提前|改到|改成|移到|换到|往后|往前|删掉|删除|取消).{0,12}(任务|安排|计划|课|复习)|"
                           r"(任务|安排|计划|课).{0,12}(挪|推迟|延后|提前|改到|改成|移到|往后|往前|删掉|删除|取消)")
QA_INTENT = re.compile(r"(怎么|如何|为什么|是什么|什么是|有哪些|区别|推荐|讲讲|解释)")
PLAN_INTENT = re.compile(r"(安排|排一下|排个|计划|规划|帮我排|日程|今晚|明天|这周|下周|每天|天内|周内)")

RULE_NO_MODEL = "（当前使用本地规则引擎。点右上角「模型设置」接入大模型后，我就能理解更复杂的需求。）"


def _rule_turn(db: Session, user: User, history: List[dict], state: TurnState, keep_engine: bool = True) -> Iterator[dict]:
    """没有可用模型：规则引擎只会排学习任务；加课、修改已有内容、答疑给出友好说明。"""
    if keep_engine:
        state.engine, state.model = "rule", "本地规则引擎"
    else:
        state.engine = "rule"
    message = _last_user(history)
    wants_plan = bool(PLAN_INTENT.search(message))
    if CHANGE_INTENT.search(message):
        state.content = ("通过对话修改已有的任务或课程需要接入大模型。你也可以在「日程」页长按任务多选后批量移动或删除，"
                         "在「课表」页点课程直接修改。" + RULE_NO_MODEL)
        yield _event("text", delta=state.content)
        return
    if COURSE_INTENT.search(message) and not wants_plan:
        state.content = ("往课表里添加课程需要接入大模型来理解星期、节次和周次。你也可以在「课表」页点「+」手动添加，"
                         "或用「导入课表」从教务系统导入。" + RULE_NO_MODEL)
        yield _event("text", delta=state.content)
        return
    if QA_INTENT.search(message) and not wants_plan:
        state.content = ("本地规则引擎只会根据课表排学习计划，回答学习问题需要接入大模型。"
                         "你可以说「这周每天两小时复习高数」让我帮你排日程。" + RULE_NO_MODEL)
        yield _event("text", delta=state.content)
        return
    try:
        draft = planner.generate_draft(db, user, message[:500] or "安排学习", use_ai=False, memory=state.memory)
    except ApiError as error:
        state.content = error.message
        yield _event("text", delta=state.content)
        return
    state.memory = draft.get("memory")
    state.content = (draft.get("reply") or "") + "\n\n" + (draft.get("advice") or "")
    if COURSE_INTENT.search(message):
        state.content += "\n\n课程需要接入大模型才能识别，可以在「课表」页手动添加。"
    if keep_engine:
        state.content += "\n\n" + RULE_NO_MODEL
    yield _event("text", delta=state.content)
    yield from _draft_proposals(state, draft)
