"""
1.2 第二批：课表识别读出节次时间（不一致时可一并更新）、专注切出次数与"没切出"奖励。
模型调用都是本地假响应。
"""

import json

from conftest import body
from test_import_ai import _provider, _recognize, png_bytes
from test_llm import completion, fake_llm  # noqa: F401 - fake_llm 是夹具

from app.ai import vision

COURSES = [{"course_name": "高等数学", "day_of_week": 1, "start_period": 1, "end_period": 2, "week_text": "1-16周"}]
PRINTED = [{"period": i + 1, "start": f"{8 + i:02d}:10", "end": f"{8 + i:02d}:55"} for i in range(12)]


def test_detected_period_times_validation():
    ok = vision.detected_period_times(PRINTED)
    assert ok[0] == {"start": "08:10", "end": "08:55"} and len(ok) == 12
    # 没有 period 字段时按顺序编号；"8:10" 补成两位
    assert vision.detected_period_times([{"start": "8:10", "end": "8:55"}, {"start": "9:05", "end": "9:50"},
                                         {"start": "10:10", "end": "10:55"}, {"start": "11:05", "end": "11:50"}])[0]["start"] == "08:10"
    assert vision.detected_period_times(PRINTED[:3]) is None, "少于 4 节不采用"
    assert vision.detected_period_times([{**p, "start": "25:00"} if p["period"] == 2 else p for p in PRINTED]) is None
    shuffled = [PRINTED[1], PRINTED[0], *PRINTED[2:]]
    assert vision.detected_period_times(shuffled)[0]["start"] == "08:10", "按节次排序"
    overlapping = [dict(p) for p in PRINTED]
    overlapping[3]["start"] = "10:30"  # 早于第 3 节结束
    assert vision.detected_period_times(overlapping) is None
    assert vision.detected_period_times(None) is None and vision.detected_period_times("08:00") is None


def test_recognition_returns_printed_period_times_and_commit_applies_them(client, register, fake_llm):  # noqa: F811
    calls, queue = fake_llm
    headers, _ = register()
    _provider(client, headers, "qwen-vl-plus")
    queue.append(completion(json.dumps({"courses": COURSES, "period_times": PRINTED}, ensure_ascii=False)))
    preview = body(_recognize(client, headers, "课表.png", png_bytes()))
    assert preview["period_times"][0] == {"start": "08:10", "end": "08:55"}
    # 预览里的上课时间仍按当前设置算，确认后才改
    assert preview["courses"][0]["start_time"] == "08:00"
    committed = body(client.post("/import/timetable/commit", headers=headers, json={
        "courses": preview["courses"], "period_times": preview["period_times"]}))
    assert committed["courses"][0]["start_time"] == "08:10" and committed["courses"][0]["end_time"] == "09:55"
    table = body(client.get("/timetable", headers=headers))
    assert table["period_times"][0] == {"start": "08:10", "end": "08:55"}

    # 和当前设置一样时不再提示
    queue.append(completion(json.dumps({"courses": COURSES, "period_times": PRINTED}, ensure_ascii=False)))
    again = body(_recognize(client, headers, "课表.png", png_bytes()))
    assert again["period_times"] is None


def test_commit_period_times_to_new_set_keeps_old_set(client, register):
    headers, _ = register()
    times = [{"start": p["start"], "end": p["end"]} for p in PRINTED]
    body(client.post("/import/timetable/commit", headers=headers, json={"courses": COURSES}))
    body(client.post("/import/timetable/commit", headers=headers, json={
        "courses": COURSES, "period_times": times, "target": "new", "set_name": "辅修"}))
    table = body(client.get("/timetable", headers=headers))
    assert table["period_times"][0]["start"] == "08:10" and table["courses"][0]["start_time"] == "08:10"
    old = next(s for s in table["sets"]["items"] if s["name"] != "辅修")
    body(client.post(f"/timetable/sets/{old['id']}/activate", headers=headers))
    back = body(client.get("/timetable", headers=headers))
    assert back["period_times"][0]["start"] == "08:00", "原来那套的节次时间不受影响"
    # 节次表不合法时拒绝
    bad = [dict(t) for t in times]
    bad[1]["start"] = "07:00"
    body(client.post("/import/timetable/commit", headers=headers, json={"courses": COURSES, "period_times": bad}), 422)


def _xp_reasons(client, headers):
    from app.core.database import SessionLocal
    from app.models import User, XpEvent

    me = body(client.get("/users/me", headers=headers))
    db = SessionLocal()
    try:
        return [e.reason for e in db.query(XpEvent).filter(XpEvent.user_id == me["id"]).all()]
    finally:
        db.close()


def test_focus_distractions_recorded_and_bonus_only_when_zero(client, register):
    headers, _ = register()
    clean = body(client.post("/study/record", headers=headers, json={
        "duration_minutes": 25, "planned_minutes": 25, "completed": True, "distractions": 0, "session_id": "s-clean"}))
    assert clean["record"]["distractions"] == 0
    assert _xp_reasons(client, headers).count("no_distraction") == 1
    body(client.post("/study/record", headers=headers, json={
        "duration_minutes": 25, "planned_minutes": 25, "completed": True, "distractions": 2, "session_id": "s-two"}))
    # 没开防切出（不传）也不发
    untracked = body(client.post("/study/record", headers=headers, json={
        "duration_minutes": 25, "planned_minutes": 25, "completed": True, "session_id": "s-none"}))
    assert untracked["record"]["distractions"] is None
    # 提前结束的不算完整番茄，也不发
    body(client.post("/study/record", headers=headers, json={
        "duration_minutes": 10, "planned_minutes": 25, "completed": False, "distractions": 0, "session_id": "s-short"}))
    assert _xp_reasons(client, headers).count("no_distraction") == 1


# ---------------------------------------------------------------- 一键排今天（规则排程）
def _future(days):
    from datetime import timedelta

    from app.core import timeutil

    return (timeutil.today() + timedelta(days=days)).isoformat()


def test_auto_plan_orders_and_spaces_items_and_commit_writes_them(client, register):
    from app.core import timeutil

    headers, _ = register()
    day = _future(1)  # 用明天：今天的空闲段取决于跑测试的时刻
    report = body(client.post("/task/create", headers=headers, json={"title": "交实验报告", "due_date": day, "duration_minutes": 30, "priority": 3}))
    inbox = body(client.post("/task/create", headers=headers, json={"title": "整理错题本", "duration_minutes": 20, "priority": 2}))
    body(client.post("/task/create", headers=headers, json={"title": "低优先级收集箱", "duration_minutes": 20, "priority": 0}))
    body(client.post("/exams", headers=headers, json={"title": "数据结构期中", "subject": "数据结构", "exam_date": _future(6)}))

    plan = body(client.get("/day/auto-plan", headers=headers, params={"date": day}))
    titles = [i["title"] for i in plan["items"]]
    assert "交实验报告" in titles and "整理错题本" in titles and "数据结构：考前复习" in titles
    assert "低优先级收集箱" not in titles, "收集箱里只取高 / 中优先级"
    exam = next(i for i in plan["items"] if i["kind"] == "exam")
    assert exam["minutes"] == 45 and exam["reason"] == "离考试 5 天"
    # 按时间排好、互不重叠，相邻两段之间至少留出休息时间
    spans = [(timeutil.hm_to_minutes(i["start_time"]), timeutil.hm_to_minutes(i["end_time"])) for i in plan["items"]]
    assert spans == sorted(spans) and all(b[0] - a[1] >= 10 for a, b in zip(spans, spans[1:]))
    assert plan["planned_minutes"] == 30 + 20 + 45 and plan["planned_minutes"] <= plan["cap_minutes"]

    result = body(client.post("/day/auto-plan/commit", headers=headers, json={"items": plan["items"]}))
    assert result["ok_count"] == 3 and result["fail_count"] == 0
    moved = body(client.get(f"/task/detail/{report['id']}", headers=headers))
    placed = next(i for i in plan["items"] if i.get("task_id") == report["id"])
    assert moved["due_date"] == day and moved["start_time"] == placed["start_time"]
    assert body(client.get(f"/task/detail/{inbox['id']}", headers=headers))["due_date"] == day
    created = next(r for r in result["results"] if r["created"])
    assert created["task"]["title"] == "数据结构：考前复习" and created["task"]["source"] == "auto"
    before = next(r for r in result["results"] if r.get("id") == report["id"])["before"]
    assert before == {"due_date": day, "start_time": None, "duration_minutes": 30}, "返回原来的状态，便于撤销"

    # 再排一次：待办都定好了时间，这一科当天也有了复习，不再重复
    again = body(client.get("/day/auto-plan", headers=headers, params={"date": day}))
    assert again["items"] == []
    # 同一条重复提交：和刚写入的复习重叠，逐条报原因
    dup = body(client.post("/day/auto-plan/commit", headers=headers, json={"items": [exam]}))
    assert dup["ok_count"] == 0 and "重叠" in dup["results"][0]["reason"]


def test_auto_plan_rejects_past_dates_and_other_users_tasks(client, register):
    alice, _ = register()
    bob, _ = register()
    body(client.get("/day/auto-plan", headers=alice, params={"date": "2000-01-01"}), 422)
    secret = body(client.post("/task/create", headers=bob, json={"title": "别人的任务", "duration_minutes": 30}))
    item = {"kind": "task", "task_id": secret["id"], "title": "别人的任务", "date": _future(1), "start_time": "09:00", "minutes": 30}
    result = body(client.post("/day/auto-plan/commit", headers=alice, json={"items": [item]}))
    assert result["ok_count"] == 0 and "不存在" in result["results"][0]["reason"]
    assert body(client.get(f"/task/detail/{secret['id']}", headers=bob))["due_date"] is None


def test_auto_plan_review_goes_after_the_class(client, register):
    from app.core import timeutil

    headers, _ = register()
    day = _future(1)
    weekday = timeutil.parse_date(day).isoweekday()
    # 第 5-6 节 14:00-15:35
    body(client.post("/timetable", headers=headers, json={
        "course_name": "线性代数", "day_of_week": weekday, "start_period": 5, "end_period": 6}))
    plan = body(client.get("/day/auto-plan", headers=headers, params={"date": day}))
    review = next(i for i in plan["items"] if i["kind"] == "review")
    assert review["optional"] is True and review["minutes"] == 15
    assert review["start_time"] >= "15:35", review


def test_reward_reports_first_check_in_of_the_day(client, register):
    headers, _ = register()
    task = body(client.post("/task/create", headers=headers, json={"title": "今天第一件事", "due_date": _future(0)}))
    other = body(client.post("/task/create", headers=headers, json={"title": "第二件事", "due_date": _future(0)}))
    first = body(client.put(f"/task/complete/{task['id']}", headers=headers))
    assert first["reward"]["checked_in_now"] is True and first["reward"]["streak"]["active_today"] is True
    second = body(client.put(f"/task/complete/{other['id']}", headers=headers))
    assert second["reward"]["checked_in_now"] is False, "当天已打卡后不再播放"
