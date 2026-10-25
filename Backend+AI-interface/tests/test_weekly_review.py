"""
每周 AI 复盘：统计口径、规则复盘、模型复盘与失败回退、缓存与 refresh、参数校验、数据隔离。
模型调用被替换为本地假响应，不会访问外网。
"""

import json
from datetime import timedelta

import pytest
from conftest import body

from app.ai import llm
from app.core import timeutil
from app.core.database import SessionLocal
from app.models import FocusRecord, StudyTask


class FakeResponse:
    def __init__(self, payload):
        self._data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def fake_llm(monkeypatch):
    calls, queue = [], []

    def urlopen(request, timeout=None):
        calls.append(json.loads(request.data) if request.data else None)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)
    return calls, queue


def completion(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def last_monday():
    return timeutil.monday_of(timeutil.today()) - timedelta(days=7)


def seed_week(user_id: int):
    """上一完整周：专注 4 天共 150 分钟；4 个截止在本周的任务（完成 3 个，逾期 2 个都是线代）。"""
    w = last_monday()
    at = lambda offset, hm="20:00": timeutil.combine(w + timedelta(days=offset), hm)  # noqa: E731
    db = SessionLocal()
    try:
        for offset, subject, minutes in ((0, "高数", 60), (1, "高数", 30), (2, "英语", 45), (6, "英语", 15), (-7, "英语", 35)):
            db.add(FocusRecord(user_id=user_id, record_date=(w + timedelta(days=offset)).isoformat(),
                               duration_minutes=minutes, subject=subject))
        tasks = [
            ("高数作业", "高数", 0, at(0)),
            ("线代习题", "线代", 1, None),
            ("线代复习", "线代", 2, at(4)),
            ("英语单词", "英语", 3, at(3)),
        ]
        for title, subject, offset, done_at in tasks:
            db.add(StudyTask(user_id=user_id, title=title, subject=subject,
                             due_date=(w + timedelta(days=offset)).isoformat(),
                             completed=done_at is not None, status="completed" if done_at else "todo",
                             completed_at=done_at))
        db.commit()
    finally:
        db.close()


def use_model(client, headers):
    body(client.post("/ai/providers", headers=headers, json={
        "name": "测试模型", "base_url": "https://m.example.com/v1", "model": "m1", "api_key": "sk-x"}))


def test_stats_and_rule_review(client, register):
    headers, user = register()
    seed_week(user["id"])
    data = body(client.get("/ai/review/weekly", headers=headers))

    w = last_monday()
    assert data["week_start"] == w.isoformat() and data["week_end"] == (w + timedelta(days=6)).isoformat()
    stats = data["stats"]
    assert stats["plan_completion_rate"] == 75
    assert stats["tasks_done"] == 3 and stats["tasks_overdue"] == 2
    assert stats["focus_minutes"] == 150 and stats["focus_days"] == 4
    assert stats["subjects"] == [{"subject": "高数", "minutes": 90}, {"subject": "英语", "minutes": 60}]
    assert stats["top_procrastinated"] == ["线代"]
    assert stats["compare"] == {"focus_minutes_delta": 115, "tasks_done_delta": 3}
    assert stats["streak_start"] == 0 and stats["streak_end"] == 1

    assert data["provider"] == "rule" and data["model"] is None and data["generated_at"]
    # 分钟格式化成"2 小时 30 分钟"
    assert "2 小时 30 分钟" in data["review_markdown"] and "75%" in data["review_markdown"]
    assert 3 <= len(data["suggestions"]) <= 6
    assert any("线代" in s for s in data["suggestions"])

    # 第二次直接读缓存
    again = body(client.get("/ai/review/weekly", headers=headers))
    assert again["cached"] is True and again["generated_at"] == data["generated_at"]


def test_empty_week_and_week_alignment(client, register):
    headers, _ = register()
    w = last_monday()
    data = body(client.get("/ai/review/weekly", headers=headers,
                           params={"week_start": (w + timedelta(days=3)).isoformat()}))
    assert data["week_start"] == w.isoformat()
    stats = data["stats"]
    assert stats["plan_completion_rate"] is None and stats["focus_minutes"] == 0 and stats["subjects"] == []
    assert "重新开始" in data["review_markdown"] and len(data["suggestions"]) >= 3

    # 本周可以复盘（进行中），下周不行；格式不对 422
    this_week = body(client.get("/ai/review/weekly", headers=headers,
                                params={"week_start": timeutil.today().isoformat()}))
    assert this_week["in_progress"] is True
    future = (timeutil.monday_of(timeutil.today()) + timedelta(days=7)).isoformat()
    body(client.get("/ai/review/weekly", headers=headers, params={"week_start": future}), 422)
    body(client.get("/ai/review/weekly", headers=headers, params={"week_start": "2025/01/01"}), 422)


def test_llm_review_cache_refresh_and_fallback(client, register, fake_llm):
    calls, queue = fake_llm
    headers, user = register()
    seed_week(user["id"])
    use_model(client, headers)

    queue.append(completion(json.dumps({
        "review_markdown": "### 本周\n- 专注 150 分钟，完成率 75%",
        "suggestions": ["线代放到上午先做", "每天至少一个番茄", "", "周日复盘"],
    }, ensure_ascii=False)))
    data = body(client.get("/ai/review/weekly", headers=headers))
    assert data["provider"] == "llm" and data["model"] == "测试模型 · m1"
    assert data["review_markdown"].startswith("### 本周")
    assert data["suggestions"] == ["线代放到上午先做", "每天至少一个番茄", "周日复盘"]
    sent = calls[0]["messages"][1]["content"]
    assert '"tasks_overdue": 2' in sent and "线代" in sent

    # 缓存命中不再调用模型
    body(client.get("/ai/review/weekly", headers=headers))
    assert len(calls) == 1

    # refresh=1 重新生成；模型返回不完整时用规则兜底并说明原因
    queue.append(completion('{"review_markdown": ""}'))
    data = body(client.get("/ai/review/weekly", headers=headers, params={"refresh": 1}))
    assert len(calls) == 2 and data["provider"] == "rule" and "fallback_reason" in data
    assert data["cached"] is False


def test_review_is_isolated_per_user(client, register):
    alice, alice_user = register()
    bob, _ = register()
    seed_week(alice_user["id"])
    assert body(client.get("/ai/review/weekly", headers=alice))["stats"]["focus_minutes"] == 150
    assert body(client.get("/ai/review/weekly", headers=bob))["stats"]["focus_minutes"] == 0
