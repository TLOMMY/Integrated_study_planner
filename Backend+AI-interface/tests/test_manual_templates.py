"""
使用手册「本地规则引擎」一节的输入模板与例句。

手册直接渲染 Frontend/src/manual/rule-templates.json；这里逐条断言其中的例句确实能被 nlu.parse_request
按写明的方式解析，并通过真实接口（/ai/plan 规则引擎、对话智能体无模型时）验证排程默认值与多轮沿用。
改了解析规则导致这里失败时，要同步改手册里的模板，不能只改测试。
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from conftest import body

from app.ai.nlu import parse_request
from app.core import timeutil

TEMPLATES = json.loads(
    (Path(__file__).resolve().parents[2] / "Frontend" / "src" / "manual" / "rule-templates.json").read_text("utf-8")
)
REF = date.fromisoformat(TEMPLATES["ref_date"])
EXAMPLES = [(group["id"], example) for group in TEMPLATES["groups"] for example in group["examples"]]


def test_reference_date_is_wednesday_as_documented():
    assert REF.weekday() == 2 and "周三" in TEMPLATES["ref_label"]
    assert len(EXAMPLES) >= 20
    for group in TEMPLATES["groups"]:
        assert group["patterns"] and group["examples"], group["id"]


@pytest.mark.parametrize("group,example", EXAMPLES, ids=[e["text"] for _, e in EXAMPLES])
def test_manual_example_is_parsed_as_documented(group, example):
    expect = example["expect"]
    parsed = parse_request(example["text"], REF, example.get("courses", []))
    if "offset" in expect:
        assert (parsed["start"] - REF).days == expect["offset"]
    else:
        # 没写日期：从今天开始，天数交给排程的默认值
        assert parsed["start"] == REF
    assert parsed["days"] == expect.get("days")
    assert parsed["prefer"] == expect.get("prefer")
    assert parsed["daily_minutes"] == expect.get("minutes")
    assert parsed["intensity"] == expect.get("intensity", 1.0)
    assert parsed["exam"] is expect.get("exam", False)
    assert parsed["subjects"] == expect["subjects"]
    deadline = parsed.get("deadline")
    if "deadline" in expect:
        assert deadline and (deadline - REF).days == expect["deadline"]
    else:
        assert deadline is None


def test_this_week_rolls_over_after_friday():
    """手册：周六、周日说“这周”会顺延到下周日（周五说仍是周五到周日 3 天）。"""
    friday, saturday, sunday = date(2026, 10, 23), date(2026, 10, 24), date(2026, 10, 25)
    assert parse_request("这周复习高数", friday, [])["days"] == 3
    rolled = parse_request("这周复习高数", saturday, [])
    assert rolled["days"] == 9 and rolled["extended"] == 2
    rolled = parse_request("这周复习高数", sunday, [])
    assert rolled["days"] == 8 and rolled["extended"] == 1


@pytest.mark.parametrize("case", TEMPLATES["planner"], ids=[c["text"] for c in TEMPLATES["planner"]])
def test_planner_defaults_and_intensity(client, auth, case):
    """默认天数（平时 7 / 备考 14）、默认每天时长（每日目标 60 分钟 ×2）、强度系数与 30-360 的上下限。"""
    draft = body(client.post("/ai/plan", headers=auth, json={"message": case["text"], "use_ai": False}))
    assert draft["provider"] == "rule" and draft["model"] == "本地规则引擎"
    assert draft["days"] == case["days"]
    assert draft["daily_minutes"] == case["daily_minutes"]


def test_followup_keeps_previous_round(client, auth):
    """手册「接着上一轮改」：加上科目 / 只改时长 / 只改天数，其余沿用。"""
    today = timeutil.today()
    next_monday = today + timedelta(days=7 - today.weekday())
    memory = None
    for turn in TEMPLATES["conversation"]:
        payload = {"message": turn["text"], "use_ai": False}
        if memory:
            payload["memory"] = memory
        draft = body(client.post("/ai/plan", headers=auth, json=payload))
        expect = turn["expect"]
        assert draft["subjects"] == expect["subjects"], turn["text"]
        assert draft["days"] == expect["days"], turn["text"]
        assert draft["daily_minutes"] == expect["daily_minutes"], turn["text"]
        assert draft["start_date"] == next_monday.isoformat(), turn["text"]
        memory = draft["memory"]


# 只用相对未来的日期：不受运行当天是几号影响，也不会因为“今天已经很晚”没有空闲
CHAT_SAMPLES = [
    "明天复习英语 90 分钟",
    "下周每天一小时复习英语",
    "明天起 5 天，每天 1 小时复习线代",
    "两周内准备期末考试，每天两小时",
    "每周三次复习高数",
]


def _chat(client, headers, message):
    cid = body(client.post("/ai/conversations", headers=headers, json={}))["id"]
    response = client.post(f"/ai/conversations/{cid}/chat", headers=headers, json={"message": message})
    assert response.status_code == 200
    events = []
    for block in response.text.strip().split("\n\n"):
        name = data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if name:
            events.append((name, data))
    assert events[-1][0] == "done", events
    return events[-1][1]["message"]


@pytest.mark.parametrize("text", CHAT_SAMPLES)
def test_manual_examples_produce_task_proposal_in_rule_chat(client, auth, text):
    """未接入模型时，在 AI 对话里输入手册例句会得到规则引擎生成的任务卡片（而不是“需要大模型”的说明）。"""
    message = _chat(client, auth, text)
    assert message["meta"]["engine"] == "rule"
    proposals = message["meta"]["proposals"]
    assert proposals and proposals[0]["type"] == "tasks" and proposals[0]["items"]


# ---------------------------------------------------------------- 新手教程完成状态
def test_onboarding_flag_saved_per_account(client, register):
    headers, user = register()
    other, _ = register()
    assert user["onboarded"] is False
    data = body(client.put("/users/me/onboarding", headers=headers, json={"done": True}))
    assert data["onboarded"] is True
    assert body(client.get("/users/me", headers=headers))["onboarded"] is True
    # 不影响其他账号
    assert body(client.get("/users/me", headers=other))["onboarded"] is False
    # 可以重置（“重新查看新手教程”不需要重置，这里只验证接口）
    assert body(client.put("/users/me/onboarding", headers=headers, json={"done": False}))["onboarded"] is False
    assert client.put("/users/me/onboarding", json={"done": True}).status_code == 401


def test_demo_account_never_auto_shows_onboarding(client):
    data = body(client.post("/auth/demo"))
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    assert data["user"]["onboarded"] is True
    # 共用的演示账号不记录状态，重置也仍视为已看过
    assert body(client.put("/users/me/onboarding", headers=headers, json={"done": False}))["onboarded"] is True
