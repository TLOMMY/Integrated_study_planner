"""v4 任务扩展：子任务、标签与清单、学习资源链接、提醒时间。"""

from datetime import timedelta

from conftest import body

from app.core import timeutil


def _create(client, headers, **fields):
    payload = {"title": "复习高数", "duration_minutes": 45, **fields}
    return body(client.post("/task/create", headers=headers, json=payload))


def _iso(day, hm):
    return f"{day.isoformat()}T{hm}"


def test_extras_roundtrip_and_defaults(client, auth):
    plain = _create(client, auth)
    assert plain["tags"] == [] and plain["checklist"] == [] and plain["links"] == []
    assert plain["list_name"] == "" and plain["remind_at"] is None
    assert (plain["checklist_done"], plain["checklist_total"]) == (0, 0)

    today = timeutil.today()
    task = _create(
        client, auth,
        due_date=today.isoformat(), start_time="19:00",
        tags=["#数学", "期末", "数学", " "], list_name="考研",
        checklist=[{"title": "看第三章"}, {"id": "b", "title": "做习题", "done": True}],
        links=[{"title": "高数精讲", "url": "https://www.bilibili.com/video/BV1xx"},
               {"url": "https://b23.tv/abc"}, {"title": "讲义", "url": "http://example.com/a.pdf", "source": "ai"}],
        remind_at=_iso(today, "18:45"),
    )
    assert task["tags"] == ["数学", "期末"]
    assert task["list_name"] == "考研"
    assert [c["title"] for c in task["checklist"]] == ["看第三章", "做习题"]
    assert all(c["id"] for c in task["checklist"])
    assert (task["checklist_done"], task["checklist_total"]) == (1, 2)
    assert [link["source"] for link in task["links"]] == ["bilibili", "bilibili", "ai"]
    assert task["links"][1]["title"] == "b23.tv"
    assert task["remind_at"] == _iso(today, "18:45")

    # 只改部分字段：其余保持；显式传 null 清除提醒
    updated = body(client.put(f"/task/update/{task['id']}", headers=auth, json={"tags": ["英语"], "remind_at": None}))
    assert updated["tags"] == ["英语"] and updated["list_name"] == "考研" and updated["remind_at"] is None
    assert len(updated["links"]) == 3


def test_extras_validation(client, auth):
    bad = [
        {"links": [{"url": "javascript:alert(1)"}]},
        {"links": [{"url": "ftp://example.com/file"}]},
        {"links": [{"url": "https://exa mple.com"}]},
        {"links": [{"title": "x" * 101, "url": "https://example.com"}]},
        {"links": [{"url": f"https://example.com/{i}"} for i in range(11)]},
        {"tags": ["这是一个超过十二个字的很长标签名"]},
        {"tags": ["a", "b", "c", "d", "e", "f"]},
        {"list_name": "清" * 21},
        {"checklist": [{"title": "x" * 101}]},
        {"checklist": [{"title": f"第{i}步"} for i in range(31)]},
        {"checklist": [{"title": ""}]},
        {"remind_at": "明天早上"},
        {"remind_at": "2026-02-30T09:00"},
    ]
    for extra in bad:
        body(client.post("/task/create", headers=auth, json={"title": "校验", **extra}), 422)
    task = _create(client, auth)
    body(client.put(f"/task/update/{task['id']}", headers=auth, json={"links": [{"url": "data:text/html,hi"}]}), 422)
    # 上限本身是允许的
    ok = _create(client, auth, tags=["a", "b", "c", "d", "e"], checklist=[{"title": str(i)} for i in range(30)],
                 links=[{"url": f"https://example.com/{i}"} for i in range(10)])
    assert len(ok["tags"]) == 5 and ok["checklist_total"] == 30 and len(ok["links"]) == 10


def test_checklist_endpoint(client, auth):
    task = _create(client, auth, checklist=[{"id": "a", "title": "一"}, {"id": "b", "title": "二"}])
    saved = body(client.put(f"/task/checklist/{task['id']}", headers=auth,
                            json={"checklist": [{"id": "b", "title": "二", "done": True}, {"id": "a", "title": "一"},
                                                {"title": "三"}]}))
    assert [c["title"] for c in saved["checklist"]] == ["二", "一", "三"]
    assert (saved["checklist_done"], saved["checklist_total"]) == (1, 3)
    assert body(client.put(f"/task/checklist/{task['id']}", headers=auth, json={"checklist": []}))["checklist_total"] == 0


def test_filters_by_list_and_tag_and_search(client, auth):
    today = timeutil.today().isoformat()
    _create(client, auth, title="背单词", due_date=today, list_name="考研", tags=["英语"])
    _create(client, auth, title="社团海报", due_date=today, list_name="社团", tags=["设计"])
    _create(client, auth, title="真题", due_date=today, list_name="考研", tags=["数学", "真题"])
    _create(client, auth, title="散活", due_date=today, tags=["英语词汇"])

    titles = lambda **params: {t["title"] for t in body(client.get("/task/list", headers=auth, params={"view": "today", **params}))["items"]}  # noqa: E731
    assert titles(list_name="考研") == {"背单词", "真题"}
    assert titles(list_name="") == {"散活"}
    # 标签精确匹配："英语" 不会匹配到 "英语词汇"
    assert titles(tag="英语") == {"背单词"}
    assert titles(tag="#真题", list_name="考研") == {"真题"}
    # 搜索也匹配标签和清单名
    search = lambda q: {t["title"] for t in body(client.get("/task/list", headers=auth, params={"view": "all", "q": q}))["items"]}  # noqa: E731
    assert search("设计") == {"社团海报"}
    assert search("考研") == {"背单词", "真题"}

    groups = body(client.get("/task/lists", headers=auth))
    lists = {g["name"]: g for g in groups["lists"]}
    assert lists["考研"]["total"] == 2 and lists["考研"]["open"] == 2
    assert {g["name"] for g in groups["tags"]} == {"英语", "设计", "数学", "真题", "英语词汇"}


def test_rename_and_clear_groups(client, auth):
    a = _create(client, auth, title="A", list_name="社团", tags=["活动", "周末"])
    b = _create(client, auth, title="B", list_name="社团", tags=["周末"])
    c = _create(client, auth, title="C", list_name="学生会", tags=["例会"])

    renamed = body(client.put("/task/lists/rename", headers=auth, json={"old_name": "社团", "new_name": "学生会"}))
    assert renamed["count"] == 2
    lists = {g["name"]: g["total"] for g in body(client.get("/task/lists", headers=auth))["lists"]}
    assert lists == {"学生会": 3}

    # 标签合并：A 有 活动+周末，把 活动 改名为 周末 后只剩一个
    body(client.put("/task/lists/rename", headers=auth, json={"kind": "tag", "old_name": "活动", "new_name": "周末"}))
    assert body(client.get(f"/task/detail/{a['id']}", headers=auth))["tags"] == ["周末"]
    body(client.put("/task/lists/rename", headers=auth, json={"old_name": "不存在", "new_name": "x"}), 404)
    body(client.put("/task/lists/rename", headers=auth, json={"kind": "tag", "old_name": "例会", "new_name": "x" * 13}), 422)

    cleared = body(client.delete("/task/lists/学生会", headers=auth))
    assert cleared["count"] == 3
    for task in (a, b, c):
        detail = body(client.get(f"/task/detail/{task['id']}", headers=auth))
        assert detail["list_name"] == ""
    body(client.delete("/task/lists/周末", headers=auth, params={"kind": "tag"}))
    assert body(client.get(f"/task/detail/{b['id']}", headers=auth))["tags"] == []
    assert body(client.get("/task/lists", headers=auth)) == {"lists": [], "tags": [{"name": "例会", "total": 1, "open": 1}]}


def test_repeat_resets_checklist_and_shifts_reminder(client, auth):
    today = timeutil.today()
    task = _create(
        client, auth, due_date=today.isoformat(), start_time="07:30", repeat_rule="daily",
        tags=["英语"], list_name="考研", links=[{"url": "https://www.bilibili.com/video/BV1"}],
        checklist=[{"id": "a", "title": "听力", "done": True}, {"id": "b", "title": "阅读", "done": True}],
        remind_at=_iso(today, "07:20"),
    )
    result = body(client.put(f"/task/complete/{task['id']}", headers=auth))
    child = result["next_task"]
    tomorrow = today + timedelta(days=1)
    assert child["due_date"] == tomorrow.isoformat()
    assert [c["done"] for c in child["checklist"]] == [False, False]
    assert [c["title"] for c in child["checklist"]] == ["听力", "阅读"]
    assert child["tags"] == ["英语"] and child["list_name"] == "考研" and len(child["links"]) == 1
    assert child["remind_at"] == _iso(tomorrow, "07:20")


def test_batch_move_and_update_shift_reminder(client, auth):
    today = timeutil.today()
    timed = _create(client, auth, due_date=today.isoformat(), start_time="20:00", remind_at=_iso(today, "19:45"))
    dated = _create(client, auth, due_date=today.isoformat(), remind_at=_iso(today, "09:00"))
    body(client.post("/task/batch", headers=auth, json={"ids": [timed["id"], dated["id"]], "action": "move", "shift_days": 2}))
    later = today + timedelta(days=2)
    assert body(client.get(f"/task/detail/{timed['id']}", headers=auth))["remind_at"] == _iso(later, "19:45")
    assert body(client.get(f"/task/detail/{dated['id']}", headers=auth))["remind_at"] == _iso(later, "09:00")

    # 拖拽改开始时间：提醒保持"提前 15 分钟"
    moved = body(client.put(f"/task/update/{timed['id']}", headers=auth, json={"start_time": "21:30"}))
    assert moved["remind_at"] == _iso(later, "21:15")
    # 同时传了新的提醒时间就以传入的为准
    manual = body(client.put(f"/task/update/{timed['id']}", headers=auth,
                             json={"due_date": today.isoformat(), "remind_at": _iso(today, "08:00")}))
    assert manual["remind_at"] == _iso(today, "08:00")
    # 从"只有日期"变成"有具体时刻"时不平移
    fixed = body(client.put(f"/task/update/{dated['id']}", headers=auth, json={"start_time": "14:00"}))
    assert fixed["remind_at"] == _iso(later, "09:00")


def test_reminders_endpoint(client, auth):
    now = timeutil.now()
    soon = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
    far = (now + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M")
    a = _create(client, auth, title="快到了", remind_at=soon)
    _create(client, auth, title="还早", remind_at=far)
    done = _create(client, auth, title="已完成", remind_at=soon)
    body(client.put(f"/task/complete/{done['id']}", headers=auth))
    items = body(client.get("/task/reminders", headers=auth))["items"]
    assert [i["title"] for i in items] == ["快到了"]
    assert items[0]["id"] == a["id"] and items[0]["remind_at"] == soon
    assert len(body(client.get("/task/reminders", headers=auth, params={"days": 14}))["items"]) == 2


def test_groups_and_reminders_are_isolated(client, register):
    alice, _ = register("A")
    bob, _ = register("B")
    soon = (timeutil.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    task = _create(client, alice, list_name="私人", tags=["秘密"], remind_at=soon, checklist=[{"title": "一"}])
    assert body(client.get("/task/lists", headers=bob)) == {"lists": [], "tags": []}
    assert body(client.get("/task/reminders", headers=bob))["items"] == []
    assert body(client.get("/task/list", headers=bob, params={"view": "all", "tag": "秘密"}))["items"] == []
    body(client.put(f"/task/checklist/{task['id']}", headers=bob, json={"checklist": []}), 404)
    body(client.put("/task/lists/rename", headers=bob, json={"old_name": "私人", "new_name": "偷改"}), 404)
    assert body(client.delete("/task/lists/私人", headers=bob))["count"] == 0
    detail = body(client.get(f"/task/detail/{task['id']}", headers=alice))
    assert detail["list_name"] == "私人" and detail["checklist_total"] == 1


def test_corrupted_json_columns_do_not_break_list(client, auth):
    from app.core.database import SessionLocal
    from app.models import StudyTask

    task = _create(client, auth, title="坏数据")
    with SessionLocal() as db:
        row = db.get(StudyTask, task["id"])
        row.tags, row.checklist, row.links = "not json", "{}", "[1"
        db.commit()
    detail = body(client.get(f"/task/detail/{task['id']}", headers=auth))
    assert detail["tags"] == [] and detail["checklist"] == [] and detail["links"] == []
