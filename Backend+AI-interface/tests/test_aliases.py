"""课程简称 / 别名与按字顺序包含——任务搜索、联网搜索查询展开。"""

from urllib.parse import parse_qs, urlparse

import pytest
from conftest import body
from test_search import _bili_routes, _ok_search, net  # noqa: F401 - 复用假网络夹具

from app.ai import search
from app.services import aliases


@pytest.mark.parametrize("query, expected", [
    ("高数", "高等数学"), ("高等数学", "高数"), ("线代", "线性代数"), ("概统", "概率论与数理统计"),
    ("概率论", "概率论与数理统计"), ("大物", "大学物理"), ("马原", "马克思主义基本原理"),
    ("毛概", "毛泽东思想和中国特色社会主义理论体系概论"), ("思修", "思想道德与法治"),
    ("C语言", "C语言程序设计"), ("c++", "C++程序设计"), ("ｃ＋＋", "C++程序设计"),
])
def test_expand_both_directions(query, expected):
    assert expected in aliases.expand(query)


def test_expand_inside_longer_query_and_unknown():
    variants = aliases.expand("高数作业")
    assert variants == ["高数作业", "高等数学作业"]
    # "大物实验"优先匹配更长的那条
    assert "大学物理实验" in aliases.expand("大物实验")
    assert aliases.expand("背单词") == ["背单词"]
    assert aliases.expand("  ") == []


def test_fuzzy_match_in_order():
    assert aliases.fuzzy_match("高数", "高等数学期中复习")
    assert aliases.fuzzy_match("线代", "线性代数第三章")
    assert aliases.fuzzy_match("数电", "数字电子技术实验")
    assert not aliases.fuzzy_match("数学", "数据结构学习")   # 字相隔太远
    assert not aliases.fuzzy_match("数高", "高等数学")       # 顺序不对
    assert not aliases.fuzzy_match("ab", "a--b")            # 非汉字只做普通包含
    assert aliases.matches("马原", ["马克思主义基本原理 第二章"])
    assert not aliases.matches("马原", ["高等数学"])


def test_expand_for_search():
    assert aliases.expand_for_search("高数 期末复习") == "高等数学 期末复习"
    assert aliases.expand_for_search("大物实验 报告") == "大学物理实验 报告"
    assert aliases.expand_for_search("线代速成") == "线性代数速成"
    # 已经是全称、含义太宽的简称、全称过长的都不动
    assert aliases.expand_for_search("线性代数 期末复习") == "线性代数 期末复习"
    assert aliases.expand_for_search("概率 例题") == "概率 例题"
    assert aliases.expand_for_search("C语言 入门") == "C语言 入门"
    assert aliases.expand_for_search("毛概 重点") == "毛概 重点"


def _task(client, headers, **fields):
    return body(client.post("/task/create", headers=headers, json={"title": "任务", **fields}))


def test_task_search_uses_aliases(client, register):
    headers, _ = register()
    other, _ = register()
    _task(client, headers, title="期中复习", subject="高等数学")
    _task(client, headers, title="高数作业 2.3")
    _task(client, headers, title="线性代数第三章预习")
    _task(client, headers, title="数据结构学习笔记")
    _task(client, other, title="高等数学（别人的）")

    def titles(q):
        return sorted(t["title"] for t in body(client.get("/task/list", headers=headers, params={"view": "all", "q": q}))["items"])

    assert titles("高数") == ["期中复习", "高数作业 2.3"]
    assert titles("高等数学") == ["期中复习", "高数作业 2.3"]
    assert titles("线代") == ["线性代数第三章预习"]
    assert titles("数学") == ["期中复习"]          # 不会匹配"数据结构学习"
    assert titles("高数作业") == ["高数作业 2.3"]
    assert titles("不存在的词") == []


def test_bilibili_query_expanded(net):  # noqa: F811
    calls, routes = net
    _bili_routes(routes, _ok_search())
    result = search.run("search_bilibili", {"keyword": "高数 期末复习"}, user=None, db=None)
    assert result["keyword"] == "高等数学 期末复习"
    assert parse_qs(urlparse(calls[-1]["url"]).query)["keyword"] == ["高等数学 期末复习"]
