# -*- coding: utf-8 -*-
"""
联网搜索工具（供 AI 智能体调用）。

约定接口（ai_chat 智能体按此接入）：
    TOOLS: List[dict]   OpenAI function-calling 格式的工具定义
    def run(name: str, args: dict, *, user, db) -> dict
        执行工具，返回可 JSON 序列化的结果；失败时返回 {"error": "中文原因"}，不要抛异常。
    def available_tools() -> List[dict]
        考虑开关 AI_WEB_SEARCH 后实际可用的工具（关闭时为空列表）。

工具：
  · search_bilibili —— B 站视频搜索（WBI 签名 + buvid 指纹 Cookie，免登录）
  · web_search      —— 通用网页搜索：配置了 SEARCH_PROVIDER + SEARCH_API_KEY 时用博查 / Tavily / Serper，
                       否则依次用免 Key 的 360 搜索、必应、DuckDuckGo（解析 HTML，可能不稳定）

两者结果里的每一项都带 {title, url, source}，可直接作为任务的 links。
只用标准库；超时 SEARCH_TIMEOUT（默认 8 秒）；结果在内存缓存 10 分钟。
"""

import base64
import hashlib
import html
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from app.core.config import settings

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")
CACHE_TTL = 600
CACHE_MAX = 200
MAX_BILIBILI = 8
MAX_WEB = 10
DESC_MAX = 120
SNIPPET_MAX = 160

TOOLS: List[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_bilibili",
            "description": (
                "在哔哩哔哩（B 站）搜索视频。当用户想要课程、网课、视频讲解、学习资源推荐，或者说"
                "“推荐几个 xx 的视频 / 网课”“找个 B 站教程”时使用；也可以在制定复习计划时为任务配上合适的视频。"
                "关键词用简短的中文，如“线性代数 期末复习”“高数 极限 讲解”。"
                "返回的每个视频有 title、url、source=bilibili，可直接作为任务的学习资源链接（links）。"
                "不要编造视频链接，只使用本工具返回的 url。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词，如“线性代数 期末复习”"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_BILIBILI,
                              "description": "返回条数，默认 5，最多 8"},
                    "order": {"type": "string", "enum": ["totalrank", "click", "pubdate", "dm", "stow"],
                              "description": "排序：totalrank 综合（默认）、click 最多播放、pubdate 最新发布、dm 最多弹幕、stow 最多收藏"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "通用网页搜索。当用户问到需要最新或外部信息的问题时使用，例如考试时间与报名信息、"
                "教材 / 课程资料、某个知识点的文章讲解、学习方法、MOOC 课程等；找视频优先用 search_bilibili。"
                "返回 title、url、snippet、source=web，可作为任务的学习资源链接。不要编造链接。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索词"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_WEB, "description": "返回条数，默认 5"},
                },
                "required": ["query"],
            },
        },
    },
]


class SearchError(Exception):
    """搜索失败，message 是给用户 / 模型看的中文原因。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------- 缓存
_cache: Dict[str, Tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def _cache_get(key: str) -> Optional[dict]:
    with _cache_lock:
        item = _cache.get(key)
        if item and time.time() - item[0] < CACHE_TTL:
            return item[1]
        _cache.pop(key, None)
    return None


def _cache_set(key: str, value: dict) -> None:
    with _cache_lock:
        if len(_cache) >= CACHE_MAX:
            for old in sorted(_cache, key=lambda k: _cache[k][0])[: CACHE_MAX // 4]:
                _cache.pop(old, None)
        _cache[key] = (time.time(), value)


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()
    _bili.reset()


# ---------------------------------------------------------------- HTTP
def _timeout() -> int:
    return max(2, int(getattr(settings, "SEARCH_TIMEOUT", 8) or 8))


def _fetch(url: str, *, headers: Optional[dict] = None, data: Optional[bytes] = None,
           label: str = "搜索服务") -> Tuple[bytes, dict]:
    request = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})},
                                     method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=_timeout()) as response:
            return response.read(), dict(response.headers.items())
    except urllib.error.HTTPError as error:
        if error.code == 412:
            raise SearchError(f"{label}拒绝了请求（412，触发风控），请稍后再试") from None
        if error.code in (401, 403):
            raise SearchError(f"{label}拒绝访问（{error.code}），请检查 API Key 或稍后再试") from None
        if error.code == 429:
            raise SearchError(f"{label}请求过于频繁，请稍后再试") from None
        raise SearchError(f"{label}返回错误（{error.code}）") from None
    except (socket.timeout, TimeoutError):
        raise SearchError(f"{label}响应超时") from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            raise SearchError(f"{label}响应超时") from None
        raise SearchError(f"无法连接{label}（{error.reason}）") from None
    except OSError as error:
        raise SearchError(f"无法连接{label}（{error}）") from None


def _json(raw: bytes, label: str) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise SearchError(f"{label}返回的数据无法解析") from None
    if not isinstance(value, dict):
        raise SearchError(f"{label}返回的数据格式不对")
    return value


def _clean(text, limit: Optional[int] = None) -> str:
    """去掉 HTML 标签（如 B 站的 <em class="keyword">）、反转义实体、压缩空白。"""
    text = re.sub(r"<[^>]+>", "", str(text or ""))
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _http_url(url) -> Optional[str]:
    url = str(url or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(url)
    return url if parsed.scheme in ("http", "https") and parsed.netloc else None


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- B 站
BILI_API = "https://api.bilibili.com"
BILI_HEADERS = {"Referer": "https://www.bilibili.com/", "Origin": "https://www.bilibili.com",
                "Accept": "application/json, text/plain, */*", "Accept-Language": "zh-CN,zh;q=0.9"}
BILI_ORDERS = {"totalrank", "click", "pubdate", "dm", "stow"}
BILI_ORDER_ALIASES = {"综合": "totalrank", "播放": "click", "最多播放": "click", "最新": "pubdate", "最新发布": "pubdate",
                      "弹幕": "dm", "收藏": "stow", "最多收藏": "stow"}
# 风控相关的业务码：-412 请求被拦截、-352 校验失败（多为 WBI / Cookie 问题）、-799 请求过快
BILI_RISK_CODES = {-412, -352, -799, -509}
# WBI 签名的混淆表（B 站前端公开的固定表）
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39,
    12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63,
    57, 62, 11, 36, 20, 34, 44, 52,
]
MIXIN_TTL = 3600
COOKIE_TTL = 6 * 3600


def mixin_key(img_key: str, sub_key: str) -> str:
    raw = img_key + sub_key
    return "".join(raw[i] for i in MIXIN_KEY_ENC_TAB if i < len(raw))[:32]


def wbi_sign(params: dict, key: str, ts: Optional[int] = None) -> str:
    """按 WBI 规则签名，返回带 wts 与 w_rid 的查询串（与签名时用的编码完全一致）。"""
    signed = {**params, "wts": int(ts if ts is not None else time.time())}
    signed = {k: re.sub(r"[!'()*]", "", str(v)) for k, v in sorted(signed.items())}
    # 用 %20 而不是 +：与浏览器 encodeURIComponent 一致，服务端才能算出同样的签名
    query = urllib.parse.urlencode(signed, quote_via=urllib.parse.quote)
    w_rid = hashlib.md5((query + key).encode("utf-8")).hexdigest()
    return f"{query}&w_rid={w_rid}"


class _BiliSession:
    """缓存 buvid 指纹 Cookie 与 WBI mixin key；被风控时 reset 后重新获取。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.cookie: Optional[str] = None
        self.cookie_at = 0.0
        self.key: Optional[str] = None
        self.key_at = 0.0

    def _get(self, path: str, cookie: Optional[str] = None) -> dict:
        headers = dict(BILI_HEADERS)
        if cookie:
            headers["Cookie"] = cookie
        raw, _ = _fetch(BILI_API + path, headers=headers, label="B 站")
        return _json(raw, "B 站")

    def cookies(self) -> str:
        with self.lock:
            if self.cookie and time.time() - self.cookie_at < COOKIE_TTL:
                return self.cookie
        data = self._get("/x/frontend/finger/spi").get("data") or {}
        b3, b4 = str(data.get("b_3") or ""), str(data.get("b_4") or "")
        if not b3:
            raise SearchError("获取 B 站访客身份失败，请稍后再试")
        parts = [f"buvid3={b3}", f"b_nut={int(time.time())}"]
        if b4:
            parts.append(f"buvid4={urllib.parse.quote(b4, safe='')}")
        with self.lock:
            self.cookie, self.cookie_at = "; ".join(parts), time.time()
            return self.cookie

    def wbi_key(self, cookie: str) -> str:
        with self.lock:
            if self.key and time.time() - self.key_at < MIXIN_TTL:
                return self.key
        # 未登录时 nav 返回 code=-101，但 wbi_img 照样有
        data = self._get("/x/web-interface/nav", cookie).get("data") or {}
        img = (data.get("wbi_img") or {})

        def stem(url) -> str:
            return str(url or "").rsplit("/", 1)[-1].split(".", 1)[0]

        img_key, sub_key = stem(img.get("img_url")), stem(img.get("sub_url"))
        if len(img_key + sub_key) < 64:
            raise SearchError("获取 B 站签名参数失败，请稍后再试")
        with self.lock:
            self.key, self.key_at = mixin_key(img_key, sub_key), time.time()
            return self.key

    def search(self, keyword: str, order: str) -> dict:
        cookie = self.cookies()
        key = self.wbi_key(cookie)
        query = wbi_sign({"search_type": "video", "keyword": keyword, "order": order, "page": 1}, key)
        return self._get("/x/web-interface/wbi/search/type?" + query, cookie)


_bili = _BiliSession()


def _bili_duration(text) -> Tuple[str, int]:
    """B 站时长 "62:03" / "1:02:03" → ("1:02:03", 62)。"""
    parts = [_int(p, -1) for p in str(text or "").split(":")]
    if not parts or any(p < 0 for p in parts):
        return str(text or ""), 0
    seconds = 0
    for p in parts:
        seconds = seconds * 60 + p
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    label = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    return label, max(1, round(seconds / 60)) if seconds else 0


def _count_text(value: int) -> str:
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f}亿"
    if value >= 10_000:
        return f"{value / 10_000:.1f}万"
    return str(value)


def _bili_item(raw: dict) -> Optional[dict]:
    bvid = str(raw.get("bvid") or "").strip()
    if not re.fullmatch(r"BV[0-9A-Za-z]{10}", bvid):
        return None
    duration, minutes = _bili_duration(raw.get("duration"))
    play = _int(raw.get("play"))
    pubdate = _int(raw.get("pubdate"))
    return {
        "title": _clean(raw.get("title"), 100),
        "url": f"https://www.bilibili.com/video/{bvid}",
        "source": "bilibili",
        "bvid": bvid,
        "author": _clean(raw.get("author"), 40),
        "play": play,
        "play_text": _count_text(play),
        "favorites": _int(raw.get("favorites")),
        "duration": duration,
        "duration_minutes": minutes,
        "pubdate": datetime.fromtimestamp(pubdate).strftime("%Y-%m-%d") if pubdate > 0 else None,
        "description": _clean(raw.get("description"), DESC_MAX),
        "cover": _http_url(raw.get("pic")),
    }


def search_bilibili(keyword: str, limit: int = 5, order: str = "totalrank") -> dict:
    keyword = _clean(keyword, 60)
    if not keyword:
        raise SearchError("请提供搜索关键词")
    limit = max(1, min(MAX_BILIBILI, _int(limit, 5)))
    order = BILI_ORDER_ALIASES.get(str(order or "").strip(), str(order or "totalrank").strip().lower())
    order = order if order in BILI_ORDERS else "totalrank"
    search_url = "https://search.bilibili.com/all?" + urllib.parse.urlencode({"keyword": keyword})

    cache_key = f"bili|{keyword}|{order}"
    cached = _cache_get(cache_key)
    if cached is None:
        last_error = None
        for attempt in range(2):
            data = _bili.search(keyword, order)
            code = _int(data.get("code"), -1)
            payload = data.get("data") or {}
            # 风控时 code 可能是 0，但 data 里只有 v_voucher（要求人机验证）而没有 result
            risky = code in BILI_RISK_CODES or (code == 0 and payload.get("v_voucher") and "result" not in payload)
            if code == 0 and not risky:
                items = [_bili_item(raw) for raw in payload.get("result") or [] if isinstance(raw, dict)]
                cached = {"items": [item for item in items if item],
                          "total": _int(payload.get("numResults"))}
                _cache_set(cache_key, cached)
                break
            if risky:
                last_error = (f"B 站触发了风控（{code}），暂时搜不到视频，请稍后再试"
                              if code != -799 else "B 站搜索请求过于频繁，请稍后再试")
                _bili.reset()  # 换一套指纹 Cookie 与签名参数重试一次
                continue
            raise SearchError(f"B 站搜索失败：{_clean(data.get('message'), 60) or code}")
        if cached is None:
            raise SearchError(last_error or "B 站搜索失败")
        from_cache = False
    else:
        from_cache = True

    results = cached["items"][:limit]
    result = {"keyword": keyword, "order": order, "results": results, "total": cached["total"],
              "search_url": search_url, "cached": from_cache}
    if not results:
        result["message"] = "B 站没有找到相关视频，换个关键词试试"
    return result


# ---------------------------------------------------------------- 通用搜索
def _web_item(title, url, snippet) -> Optional[dict]:
    url = _http_url(url)
    title = _clean(title, 100)
    if not url or not title:
        return None
    return {"title": title, "url": url, "snippet": _clean(snippet, SNIPPET_MAX), "source": "web",
            "site": urllib.parse.urlparse(url).netloc}


def _post_json(url: str, body: dict, headers: dict, label: str) -> dict:
    raw, _ = _fetch(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Accept": "application/json", **headers}, label=label)
    return _json(raw, label)


def _bocha(query: str, limit: int, key: str) -> List[dict]:
    data = _post_json("https://api.bochaai.com/v1/web-search",
                      {"query": query, "count": limit, "summary": True},
                      {"Authorization": f"Bearer {key}"}, "博查搜索")
    if _int(data.get("code"), 200) != 200:
        raise SearchError(f"博查搜索失败：{_clean(data.get('msg') or data.get('message'), 60)}")
    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    pages = ((payload.get("webPages") or {}).get("value")) or []
    return [_web_item(p.get("name"), p.get("url"), p.get("summary") or p.get("snippet")) for p in pages
            if isinstance(p, dict)]


def _tavily(query: str, limit: int, key: str) -> List[dict]:
    data = _post_json("https://api.tavily.com/search", {"query": query, "max_results": limit, "search_depth": "basic"},
                      {"Authorization": f"Bearer {key}"}, "Tavily")
    return [_web_item(r.get("title"), r.get("url"), r.get("content")) for r in data.get("results") or []
            if isinstance(r, dict)]


def _serper(query: str, limit: int, key: str) -> List[dict]:
    data = _post_json("https://google.serper.dev/search", {"q": query, "num": limit, "hl": "zh-cn"},
                      {"X-API-KEY": key}, "Serper")
    return [_web_item(r.get("title"), r.get("link"), r.get("snippet")) for r in data.get("organic") or []
            if isinstance(r, dict)]


def _ddg_target(href: str) -> str:
    """DuckDuckGo 偶尔给 //duckduckgo.com/l/?uddg=<真实地址> 形式的跳转链接。"""
    href = html.unescape(href)
    if "duckduckgo.com/l/" in href:
        target = urllib.parse.parse_qs(urllib.parse.urlparse(href if "://" in href else "https:" + href).query)
        return (target.get("uddg") or [""])[0]
    return href


def _duckduckgo(query: str, limit: int, _key=None) -> List[dict]:
    raw, _ = _fetch("https://html.duckduckgo.com/html/",
                    data=urllib.parse.urlencode({"q": query, "kl": "cn-zh"}).encode("ascii"),
                    headers={"Content-Type": "application/x-www-form-urlencoded",
                             "Accept-Language": "zh-CN,zh;q=0.9"}, label="DuckDuckGo")
    text = raw.decode("utf-8", "ignore")
    if "anomaly-modal" in text or "challenge-form" in text:
        raise SearchError("DuckDuckGo 要求人机验证")
    items = []
    for block in re.split(r'<div class="result results_links', text)[1:]:
        if "result--ad" in block[:200]:
            continue
        link = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not link:
            continue
        snippet = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, re.S)
        items.append(_web_item(link.group(2), _ddg_target(link.group(1)), snippet.group(1) if snippet else ""))
    return items


def _bing_target(href: str) -> str:
    """必应的跳转链接 bing.com/ck/a?...&u=a1<base64url> 还原成真实地址。"""
    href = html.unescape(href)
    if "bing.com/ck/a" not in href:
        return href
    value = (urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("u") or [""])[0]
    if value.startswith("a1"):
        try:
            encoded = value[2:]
            return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8", "ignore")
        except (ValueError, UnicodeDecodeError):
            return ""
    return ""


def _bing(query: str, limit: int, _key=None) -> List[dict]:
    raw, _ = _fetch("https://cn.bing.com/search?" + urllib.parse.urlencode({"q": query, "count": max(10, limit)}),
                    headers={"Accept-Language": "zh-CN,zh;q=0.9", "Accept": "text/html"}, label="必应")
    text = raw.decode("utf-8", "ignore")
    items = []
    for block in text.split('<li class="b_algo"')[1:]:
        link = re.search(r"<h2[^>]*>\s*<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", block, re.S)
        if not link:
            continue
        snippet = re.search(r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>', block, re.S) \
            or re.search(r'<div class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>', block, re.S)
        items.append(_web_item(link.group(2), _bing_target(link.group(1)), snippet.group(1) if snippet else ""))
    return items


def _so360(query: str, limit: int, _key=None) -> List[dict]:
    """360 搜索：真实地址在 data-mdurl，href 是 so.com/link 跳转（没有 data-mdurl 时退回跳转链接，同样能打开）。"""
    raw, _ = _fetch("https://www.so.com/s?" + urllib.parse.urlencode({"q": query}),
                    headers={"Accept-Language": "zh-CN,zh;q=0.9", "Accept": "text/html"}, label="360 搜索")
    text = re.sub(r"<style.*?</style>|<script.*?</script>", "", raw.decode("utf-8", "ignore"), flags=re.S)
    items = []
    # 属性前的空格数量不固定（<h3 class="res-title " > / <h3   class="res-title">）
    for block in re.split(r'<h3\s+class="res-title[\s"]', text)[1:]:
        link = re.search(r"<a([^>]*)>(.*?)</a>", block, re.S)
        if not link:
            continue
        attrs = link.group(1)
        real = re.search(r'data-mdurl="([^"]+)"', attrs) or re.search(r'href="([^"]+)"', attrs)
        snippet = re.search(r"<span data-result-summary[^>]*>(.*?)</span>", block, re.S) \
            or re.search(r'<p class="res-desc"[^>]*>(.*?)</p>', block, re.S)
        items.append(_web_item(link.group(2), html.unescape(real.group(1)) if real else "",
                               snippet.group(1) if snippet else ""))
    return items


WEB_PROVIDERS: Dict[str, Tuple[str, Callable]] = {
    "bocha": ("博查", _bocha),
    "tavily": ("Tavily", _tavily),
    "serper": ("Serper", _serper),
}
# 免 Key 引擎按顺序尝试。实测（国内网络）：360 搜索约 1 秒、结果相关；必应很快，但匿名请求遇到 3 个词以上的
# 查询常只匹配第一个词；DuckDuckGo 在国内经常超时，放最后兜底
FREE_ENGINES: List[Tuple[str, str, Callable]] = [
    ("so360", "360 搜索", _so360), ("bing", "必应", _bing), ("duckduckgo", "DuckDuckGo", _duckduckgo),
]


def web_search(query: str, limit: int = 5) -> dict:
    query = _clean(query, 100)
    if not query:
        raise SearchError("请提供搜索词")
    limit = max(1, min(MAX_WEB, _int(limit, 5)))
    provider = (getattr(settings, "SEARCH_PROVIDER", "") or "").strip().lower()
    key = getattr(settings, "SEARCH_API_KEY", None) or ""

    engines: List[Tuple[str, str, Callable]] = []
    if provider in WEB_PROVIDERS and key:
        engines.append((provider, *WEB_PROVIDERS[provider]))
    engines += FREE_ENGINES

    cache_key = f"web|{query}|{limit}|{provider}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    errors = []
    for code, label, engine in engines:
        try:
            items = [item for item in engine(query, limit, key) if item]
        except SearchError as error:
            errors.append(f"{label}：{error.message}")
            continue
        seen, results = set(), []
        for item in items:
            if item["url"] not in seen:
                seen.add(item["url"])
                results.append(item)
        if not results:
            errors.append(f"{label}：没有结果")
            continue
        result = {"query": query, "engine": code, "results": results[:limit]}
        if provider and code != provider:
            result["note"] = f"已配置的搜索服务不可用（{'；'.join(errors) or '未填写 SEARCH_API_KEY'}），改用 {label}"
        _cache_set(cache_key, result)
        return {**result, "cached": False}
    raise SearchError("联网搜索暂时不可用（" + "；".join(errors)[:200] + "）。可在 .env 配置 SEARCH_PROVIDER 与 SEARCH_API_KEY 获得稳定的搜索")


# ---------------------------------------------------------------- 对外入口
HANDLERS: Dict[str, Callable[[dict], dict]] = {
    "search_bilibili": lambda args: search_bilibili(args.get("keyword") or args.get("query") or "",
                                                    args.get("limit", 5), args.get("order") or "totalrank"),
    "web_search": lambda args: web_search(args.get("query") or args.get("keyword") or "", args.get("limit", 5)),
}


def enabled() -> bool:
    return bool(getattr(settings, "AI_WEB_SEARCH", True))


def available_tools() -> List[dict]:
    """开关关闭时返回空列表，智能体就不会把搜索工具提供给模型。"""
    return list(TOOLS) if enabled() else []


def run(name: str, args: dict, *, user=None, db=None) -> dict:
    handler = HANDLERS.get(name)
    if handler is None:
        return {"error": f"未知的搜索工具：{name}"}
    if not enabled():
        return {"error": "管理员已关闭联网搜索"}
    if isinstance(args, str):
        try:
            args = json.loads(args or "{}")
        except ValueError:
            args = {}
    if not isinstance(args, dict):
        args = {}
    try:
        return handler(args)
    except SearchError as error:
        return {"error": error.message}
    except Exception:  # noqa: BLE001 - 工具失败不能拖垮整轮对话
        return {"error": "联网搜索出错了，请稍后再试"}
