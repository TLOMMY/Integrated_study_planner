"""
联网搜索工具：WBI 签名、B 站结果清洗与风控重试、通用搜索服务商与免 Key 引擎降级、开关。
所有网络请求都被替换为本地假响应，不会访问外网。
"""

import io
import json
import urllib.error
from urllib.parse import parse_qs, urlparse

import pytest

from app.ai import search
from app.core.config import settings

NAV = {"code": -101, "data": {"wbi_img": {
    "img_url": "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
    "sub_url": "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"}}}
SPI = {"code": 0, "data": {"b_3": "AAAA-BBBB-infoc", "b_4": "CCCC==/x"}}
VIDEO = {
    "bvid": "BV1Ey4y147xn", "title": "《<em class=\"keyword\">线性代数</em>》4小时速成课 &amp; 习题",
    "author": "框框老师课堂", "play": 27115133, "favorites": 762185, "duration": "293:04",
    "pubdate": 1617840000, "description": "配套讲义" * 50, "pic": "//i2.hdslb.com/bfs/archive/x.jpg",
}


class FakeResponse:
    def __init__(self, data: bytes, headers=None):
        self._data, self.headers = data, headers or {}

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _payload(value):
    if isinstance(value, Exception):
        raise value
    if isinstance(value, (bytes, str)):
        return FakeResponse(value.encode("utf-8") if isinstance(value, str) else value)
    return FakeResponse(json.dumps(value, ensure_ascii=False).encode("utf-8"))


@pytest.fixture
def net(monkeypatch):
    """按 URL 前缀路由的假网络：routes[前缀] = 响应（或响应列表，依次返回）；记录每次请求。"""
    calls, routes = [], {}

    def urlopen(request, timeout=None):
        url = request.full_url
        calls.append({"url": url, "headers": {k.lower(): v for k, v in request.header_items()},
                      "data": request.data, "timeout": timeout})
        for prefix in sorted(routes, key=len, reverse=True):
            if url.startswith(prefix):
                value = routes[prefix]
                if isinstance(value, list):
                    value = value.pop(0) if len(value) > 1 else value[0]
                return _payload(value)
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(search.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(settings, "AI_WEB_SEARCH", True)
    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "")
    monkeypatch.setattr(settings, "SEARCH_API_KEY", None)
    search.clear_cache()
    yield calls, routes
    search.clear_cache()


def _bili_routes(routes, *search_responses):
    routes["https://api.bilibili.com/x/frontend/finger/spi"] = SPI
    routes["https://api.bilibili.com/x/web-interface/nav"] = NAV
    routes["https://api.bilibili.com/x/web-interface/wbi/search/type"] = list(search_responses)


def _ok_search(*videos):
    return {"code": 0, "data": {"numResults": 1000, "result": list(videos)}}


# ---------------------------------------------------------------- 签名
def test_wbi_sign_matches_reference_vector():
    """bilibili-API-collect 文档里的公开示例。"""
    key = search.mixin_key("7cd084941338484aae1ad9425b84077c", "4932caff0ff746eab6f01bf08b70ac45")
    assert key == "ea1db124af3c7062474693fa704f4ff8"
    signed = search.wbi_sign({"foo": "114", "bar": "514", "zab": 1919810}, key, ts=1702204169)
    assert signed == "bar=514&foo=114&wts=1702204169&zab=1919810&w_rid=8f6f2b5b3d485fe1886cec6a0be8c5d4"
    # 空格编码成 %20、过滤 !'()* 字符
    assert "keyword=a%20b" in search.wbi_sign({"keyword": "a b(!)"}, key, ts=1)


def test_tools_definitions_shape():
    names = [tool["function"]["name"] for tool in search.TOOLS]
    assert names == ["search_bilibili", "web_search"]
    for tool in search.TOOLS:
        assert tool["type"] == "function" and tool["function"]["description"]
        assert tool["function"]["parameters"]["required"]


# ---------------------------------------------------------------- B 站
def test_bilibili_search_cleans_results_and_sends_cookies(net):
    calls, routes = net
    _bili_routes(routes, _ok_search(VIDEO, {"bvid": "bad", "title": "无效"}))
    result = search.run("search_bilibili", {"keyword": "线性代数 期末复习", "limit": 3}, user=None, db=None)

    assert "error" not in result and result["total"] == 1000 and result["cached"] is False
    item = result["results"][0]
    assert item["title"] == "《线性代数》4小时速成课 & 习题"
    assert item["url"] == "https://www.bilibili.com/video/BV1Ey4y147xn" and item["source"] == "bilibili"
    assert item["duration"] == "4:53:04" and item["duration_minutes"] == 293
    assert item["play_text"] == "2711.5万" and item["pubdate"] == "2021-04-08"
    assert len(item["description"]) <= search.DESC_MAX and item["cover"].startswith("https://")
    assert len(result["results"]) == 1  # 无效 bvid 被丢弃
    assert "search.bilibili.com" in result["search_url"]

    request = calls[-1]
    query = parse_qs(urlparse(request["url"]).query)
    assert query["keyword"] == ["线性代数 期末复习"] and query["search_type"] == ["video"]
    assert "w_rid" in query and "wts" in query
    assert "buvid3=AAAA-BBBB-infoc" in request["headers"]["cookie"]
    assert "buvid4=CCCC%3D%3D%2Fx" in request["headers"]["cookie"]
    assert request["headers"]["referer"] == "https://www.bilibili.com/"
    assert request["timeout"] == settings.SEARCH_TIMEOUT

    # 10 分钟内同一关键词走缓存，不再请求；limit 不同也共用
    count = len(calls)
    again = search.run("search_bilibili", {"keyword": "线性代数 期末复习", "limit": 1}, user=None, db=None)
    assert again["cached"] is True and len(again["results"]) == 1 and len(calls) == count


def test_bilibili_risk_control_retries_once_then_reports(net):
    calls, routes = net
    _bili_routes(routes, {"code": -352, "message": "风控校验失败"}, _ok_search(VIDEO))
    result = search.run("search_bilibili", {"keyword": "高数"}, user=None, db=None)
    assert len(result["results"]) == 1
    # 重试前重新获取了指纹 Cookie 与签名参数
    assert sum("finger/spi" in c["url"] for c in calls) == 2

    search.clear_cache()
    _bili_routes(routes, {"code": 0, "data": {"v_voucher": "voucher_xxx"}})
    result = search.run("search_bilibili", {"keyword": "概率论"}, user=None, db=None)
    assert "风控" in result["error"]


def test_bilibili_http_errors_are_chinese(net):
    _, routes = net
    _bili_routes(routes, urllib.error.HTTPError("u", 412, "x", {}, io.BytesIO(b"")))
    assert "412" in search.run("search_bilibili", {"keyword": "高数"}, user=None, db=None)["error"]

    search.clear_cache()
    routes.clear()  # 没有路由 = 断网
    assert "无法连接" in search.run("search_bilibili", {"keyword": "高数"}, user=None, db=None)["error"]


def test_bilibili_order_and_bad_args(net):
    calls, routes = net
    _bili_routes(routes, _ok_search())
    result = search.run("search_bilibili", {"keyword": "高数", "order": "最多播放"}, user=None, db=None)
    assert result["order"] == "click" and result["results"] == [] and "换个关键词" in result["message"]
    assert parse_qs(urlparse(calls[-1]["url"]).query)["order"] == ["click"]
    assert search.run("search_bilibili", {"keyword": "  "}, user=None, db=None)["error"] == "请提供搜索关键词"
    # 参数是 JSON 字符串也能接受；未知工具返回错误
    assert "results" in search.run("search_bilibili", '{"keyword": "高数", "order": "bogus"}', user=None, db=None)
    assert "未知" in search.run("nope", {}, user=None, db=None)["error"]


# ---------------------------------------------------------------- 通用搜索
SO360_HTML = """<html><style>.x{}</style><ul>
<li class="res-list"><h3 class="res-title " > <a href="https://www.so.com/link?m=1" data-mdurl="https://cet.neea.edu.cn/">
<em>四级</em>考试 &amp; 报名</a></h3><p class="res-desc"><span data-result-summary>12 月 13 日举行</span></p></li>
<li class="res-list"><h3   class="res-title"><a href="javascript:void(0)">坏链接</a></h3></li>
<li class="res-list"><h3   class="res-title"><a href="https://www.so.com/link?m=2" data-mdurl="https://cet.neea.edu.cn/">重复</a></h3></li>
</ul></html>"""
BING_HTML = """<ol><li class="b_algo"><h2><a href="https://www.bing.com/ck/a?!&&p=1&u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS9wYWdl&ntb=1">
必应结果</a></h2><div class="b_caption"><p class="b_lineclamp2">摘要</p></div></li></ol>"""


def test_web_search_free_engines_in_order(net):
    calls, routes = net
    routes["https://www.so.com/s"] = SO360_HTML
    result = search.run("web_search", {"query": "四级 考试时间"}, user=None, db=None)
    assert result["engine"] == "so360"
    assert result["results"] == [{"title": "四级考试 & 报名", "url": "https://cet.neea.edu.cn/",
                                  "snippet": "12 月 13 日举行", "source": "web", "site": "cet.neea.edu.cn"}]

    # 360 失败 → 必应（跳转链接解码成真实地址）
    search.clear_cache()
    routes["https://www.so.com/s"] = urllib.error.HTTPError("u", 403, "x", {}, io.BytesIO(b""))
    routes["https://cn.bing.com/search"] = BING_HTML
    result = search.run("web_search", {"query": "四级"}, user=None, db=None)
    assert result["engine"] == "bing" and result["results"][0]["url"] == "https://example.com/page"

    # 全部失败：中文原因 + 配置提示
    search.clear_cache()
    routes.clear()
    error = search.run("web_search", {"query": "四级"}, user=None, db=None)["error"]
    assert "联网搜索暂时不可用" in error and "SEARCH_API_KEY" in error


def test_web_search_configured_provider(net, monkeypatch):
    calls, routes = net
    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "bocha")
    monkeypatch.setattr(settings, "SEARCH_API_KEY", "sk-test")
    routes["https://api.bochaai.com/v1/web-search"] = {"code": 200, "data": {"webPages": {"value": [
        {"name": "博查结果", "url": "https://a.example.com", "summary": "摘要" * 200},
        {"name": "ftp 链接", "url": "ftp://bad.example.com", "summary": ""},
    ]}}}
    result = search.run("web_search", {"query": "线性代数", "limit": 3}, user=None, db=None)
    assert result["engine"] == "bocha" and [r["title"] for r in result["results"]] == ["博查结果"]
    assert len(result["results"][0]["snippet"]) <= search.SNIPPET_MAX
    assert calls[-1]["headers"]["authorization"] == "Bearer sk-test"
    assert json.loads(calls[-1]["data"])["count"] == 3

    # 服务商出错时降级到免 Key 引擎，并说明原因
    search.clear_cache()
    routes["https://api.bochaai.com/v1/web-search"] = urllib.error.HTTPError("u", 401, "x", {}, io.BytesIO(b""))
    routes["https://www.so.com/s"] = SO360_HTML
    result = search.run("web_search", {"query": "线性代数"}, user=None, db=None)
    assert result["engine"] == "so360" and "博查" in result["note"]


@pytest.mark.parametrize("provider,url,payload,title", [
    ("tavily", "https://api.tavily.com/search",
     {"results": [{"title": "T", "url": "https://t.example.com", "content": "c"}]}, "T"),
    ("serper", "https://google.serper.dev/search",
     {"organic": [{"title": "S", "link": "https://s.example.com", "snippet": "c"}]}, "S"),
])
def test_other_providers(net, monkeypatch, provider, url, payload, title):
    _, routes = net
    monkeypatch.setattr(settings, "SEARCH_PROVIDER", provider)
    monkeypatch.setattr(settings, "SEARCH_API_KEY", "k")
    routes[url] = payload
    result = search.run("web_search", {"query": "x"}, user=None, db=None)
    assert result["engine"] == provider and result["results"][0]["title"] == title


def test_switch_off(net, monkeypatch):
    calls, _ = net
    monkeypatch.setattr(settings, "AI_WEB_SEARCH", False)
    assert search.available_tools() == []
    assert search.run("search_bilibili", {"keyword": "高数"}, user=None, db=None) == {"error": "管理员已关闭联网搜索"}
    assert calls == []
    monkeypatch.setattr(settings, "AI_WEB_SEARCH", True)
    assert len(search.available_tools()) == 2


def test_unexpected_exception_never_raises(net, monkeypatch):
    def boom(_args):
        raise RuntimeError("bug")

    monkeypatch.setitem(search.HANDLERS, "web_search", boom)
    assert search.run("web_search", {"query": "x"}, user=None, db=None) == {"error": "联网搜索出错了，请稍后再试"}
