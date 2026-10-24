from datetime import timedelta

from conftest import body

from app.ai.nlu import parse_request
from app.ai.planner import _validate_ai_tasks, free_slots
from app.core import timeutil


def test_nlu_extracts_parameters():
    ref = timeutil.today()
    parsed = parse_request("这周每天两小时复习高数和英语，晚上学", ref, ["工科数学分析(二)", "学术英语（二）"])
    assert parsed["daily_minutes"] == 120 and parsed["prefer"] == "evening"
    assert parsed["subjects"] == ["学术英语（二）", "工科数学分析(二)"] or set(parsed["subjects"]) == {
        "工科数学分析(二)", "学术英语（二）"}
    left = 7 - ref.weekday()
    # 周五以后"这周"只剩不到 3 天，会顺延到下周日
    assert parsed["days"] == (left if left >= 3 else left + 7)

    exam = parse_request("两周内准备期末考试，每天一个半小时", ref, [])
    assert exam["days"] == 14 and exam["exam"] is True and exam["daily_minutes"] == 90

    assert parse_request("第13周有考试", ref, [])["days"] is None
    assert parse_request("今晚复习线代", ref, [])["days"] == 1
    assert parse_request("轻松一点复习物理", ref, [])["intensity"] < 1


def test_free_slots_avoid_courses_and_meals():
    day = timeutil.today() + timedelta(days=3)
    slots = free_slots([("08:00", "09:35"), ("19:00", "20:35")], day)
    for slot in slots:
        start, end = timeutil.hm_to_minutes(slot["start"]), timeutil.hm_to_minutes(slot["end"])
        assert not (start < 9 * 60 + 45 and end > 8 * 60 - 10)
        assert not (start < 20 * 60 + 45 and end > 19 * 60 - 10)
        assert not (start < 13 * 60 + 30 and end > 12 * 60)
        assert end <= 22 * 60


def test_draft_is_not_saved_and_avoids_courses(client, auth):
    target = timeutil.today() + timedelta(days=2)
    body(client.post("/timetable", headers=auth, json={"course_name": "大学物理", "day_of_week": target.isoweekday(),
                                                       "start_period": 9, "end_period": 10}))
    before = body(client.get("/study-plans", headers=auth))["total"]
    draft = body(client.post("/ai/plan", headers=auth, json={"message": "复习物理，晚上学", "start_date": target.isoformat(),
                                                            "days": 1, "daily_minutes": 120}))
    assert body(client.get("/study-plans", headers=auth))["total"] == before
    assert draft["provider"] == "rule" and draft["tasks"]
    assert sum(t["duration_minutes"] for t in draft["tasks"]) <= 120
    for task in draft["tasks"]:
        start = timeutil.hm_to_minutes(task["start_time"])
        end = start + task["duration_minutes"]
        assert not (start < 20 * 60 + 35 and end > 19 * 60), task
    assert draft["stats"]["course_count"] == 1


def test_variant_changes_layout(client, auth):
    target = (timeutil.today() + timedelta(days=4)).isoformat()
    a = body(client.post("/ai/plan", headers=auth, json={"message": "复习英语", "start_date": target, "days": 1}))
    b = body(client.post("/ai/plan", headers=auth, json={"message": "复习英语", "start_date": target, "days": 1, "variant": 1}))
    assert [t["start_time"] for t in a["tasks"]] != [t["start_time"] for t in b["tasks"]]


def test_commit_creates_plan_tasks_and_achievement(client, auth):
    target = (timeutil.today() + timedelta(days=1)).isoformat()
    draft = body(client.post("/ai/plan", headers=auth, json={"message": "3天复习线性代数", "start_date": target}))
    assert draft["days"] == 3
    saved = body(client.post("/ai/plan/commit", headers=auth, json=draft))
    plan = saved["plan"]
    assert plan["source"] == "ai" and plan["task_total"] == len(draft["tasks"])
    assert {"planner", "ai_planner"} <= {a["code"] for a in saved["reward"]["new_achievements"]}
    listed = body(client.get(f"/task/list?view=range&start={draft['start_date']}&end={draft['end_date']}", headers=auth))
    assert {t["plan_id"] for t in listed["items"]} == {plan["id"]}


def test_commit_accepts_longest_plan(client, auth):
    draft = body(client.post("/ai/plan", headers=auth, json={"message": "四周内复习高数和英语，每天两小时",
                                                            "start_date": (timeutil.today() + timedelta(days=1)).isoformat()}))
    assert draft["days"] == 28 and len(draft["tasks"]) > 80
    saved = body(client.post("/ai/plan/commit", headers=auth, json=draft))
    assert saved["plan"]["task_total"] == len(draft["tasks"])


def test_commit_validates_payload(client, auth):
    body(client.post("/ai/plan/commit", headers=auth, json={"title": "空", "start_date": "2026-01-01",
                                                            "end_date": "2026-01-01", "days": 1, "tasks": []}), 422)


def test_llm_output_must_fit_free_slots():
    day = timeutil.today() + timedelta(days=5)
    contexts = [{"date": day, "free": [{"start": "14:00", "end": "16:00", "minutes": 120, "segment": "afternoon"}]}]
    tasks = [
        {"date": day.isoformat(), "start_time": "14:10", "duration_minutes": 45, "title": "合法"},
        {"date": day.isoformat(), "start_time": "15:30", "duration_minutes": 60, "title": "超出空闲"},
        {"date": "2000-01-01", "start_time": "14:10", "duration_minutes": 45, "title": "日期不对"},
        {"date": day.isoformat(), "start_time": "bad", "duration_minutes": 45, "title": "格式错"},
    ]
    valid = _validate_ai_tasks(tasks, contexts, 120)
    assert [t["title"] for t in valid] == ["合法"]
    assert _validate_ai_tasks("not a list", contexts, 120) is None
