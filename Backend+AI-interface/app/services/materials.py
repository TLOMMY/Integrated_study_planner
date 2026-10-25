# -*- coding: utf-8 -*-
"""
PDF 讲义提取章节：书签（outline）优先，没有书签时识别正文里的章节标题，都没有就按页数分段。

每个章节给出页码范围与字数，按字数（课件页数多、字少时按页数）估算复习分钟。
有可用模型时，让模型把章节整理成更合理的复习单元（合并太碎的小节、拆开太大的章节），
模型输出逐条校验（页码在文件范围内、时长合理），校验不过或调用失败时退回规则结果。
"""

import io
import json
import math
import re
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.ai import llm, providers
from app.ai.llm import LlmError
from app.core.errors import ApiError
from app.models import User

MAX_PAGES = 800
MAX_TOP = 60
MAX_CHILDREN = 30
# 复习速度：每分钟约 150 字；课件（每页字少）每页至少 1.5 分钟
CHARS_PER_MINUTE = 150
MINUTES_PER_PAGE = 1.5
MIN_MINUTES, MAX_MINUTES = 10, 240
PAGES_PER_CHUNK = 10
SCANNED_HINT = "这份 PDF 看起来是扫描件或图片，提取不到文字。请上传文字版 PDF（能选中复制文字的那种），或先用 OCR 工具转换"

_CN_NUM = "一二三四五六七八九十百零〇两"
# (正则, 层级)：层级 1 = 章，2 = 节
HEADING_PATTERNS: List[Tuple[re.Pattern, int]] = [
    (re.compile(rf"^第\s*[0-9{_CN_NUM}]+\s*[章讲篇部分单元]\s*\S.{{0,40}}$"), 1),
    (re.compile(r"^(?:Chapter|CHAPTER|Lecture|LECTURE|Unit|UNIT)\s+\d+\b.{0,60}$"), 1),
    (re.compile(rf"^[{_CN_NUM}]+\s*[、.．]\s*\S.{{0,40}}$"), 1),
    (re.compile(rf"^第\s*[0-9{_CN_NUM}]+\s*节\s*\S.{{0,40}}$"), 2),
    (re.compile(r"^\d{1,2}\.\d{1,2}\s+\S.{0,40}$"), 2),
]


# ---------------------------------------------------------------- PDF 读取
def _read_pdf(content: bytes):
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if content[:5] != b"%PDF-":
        raise ApiError(415, "仅支持 PDF 文件")
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ApiError(422, "PDF 已加密，请先解除密码再上传")
        pages = []
        for page in reader.pages[:MAX_PAGES]:
            try:
                pages.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001 - 个别页面字体损坏时跳过该页文字
                pages.append("")
        total = len(reader.pages)
    except ApiError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError):
        raise ApiError(422, "PDF 文件已损坏或无法读取") from None
    if total == 0:
        raise ApiError(422, "PDF 里没有页面")
    return reader, pages, total


def _char_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _outline_entries(reader, total: int) -> List[Tuple[int, str, int]]:
    """书签 → [(层级, 标题, 起始页 1 起)]，只取前两层。"""
    entries: List[Tuple[int, str, int]] = []

    def walk(items, level: int) -> None:
        for item in items:
            if isinstance(item, list):
                if level < 2:
                    walk(item, level + 1)
                continue
            title = re.sub(r"\s+", " ", str(getattr(item, "title", "") or "")).strip()
            try:
                page = reader.get_destination_page_number(item)
            except Exception:  # noqa: BLE001 - 指向不存在页面的书签直接跳过
                page = None
            if title and page is not None and 0 <= page < total:
                entries.append((level, title[:80], page + 1))

    try:
        walk(reader.outline or [], 1)
    except Exception:  # noqa: BLE001 - 书签结构损坏时退回正文识别
        return []
    return entries


def _heading_entries(pages: List[str]) -> List[Tuple[int, str, int]]:
    """在每页前几行里找章节标题（"第一章 …""1.2 …""Chapter 3 …"）。"""
    entries: List[Tuple[int, str, int]] = []
    seen = set()
    for index, text in enumerate(pages, start=1):
        lines = [re.sub(r"\s+", " ", line).strip() for line in (text or "").splitlines()]
        for line in [line for line in lines if line][:6]:
            for pattern, level in HEADING_PATTERNS:
                if pattern.match(line):
                    key = (level, line)
                    if key not in seen:  # 页眉里重复出现的章名只算第一次
                        seen.add(key)
                        entries.append((level, line[:80], index))
                    break
    # 只认到一两个"标题"多半是误判（如目录里的一行），不如按页分段
    return entries if len(entries) >= 2 else []


# ---------------------------------------------------------------- 章节树
def estimate_minutes(chars: int, page_count: int) -> int:
    raw = max(chars / CHARS_PER_MINUTE, page_count * MINUTES_PER_PAGE)
    return int(min(MAX_MINUTES, max(MIN_MINUTES, math.ceil(raw / 5) * 5)))


def _node(title: str, start: int, end: int, page_chars: List[int]) -> dict:
    chars = sum(page_chars[start - 1:end])
    return {"title": title, "pages": [start, end], "words": chars,
            "est_minutes": estimate_minutes(chars, end - start + 1)}


def _ranges(starts: List[int], last: int) -> List[int]:
    """每项的结束页 = 下一项起始页 - 1（同页开始则共用该页），最后一项到 last。"""
    ends = []
    for i, start in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else last + 1
        ends.append(max(start, min(last, nxt - 1)))
    return ends


def build_tree(entries: List[Tuple[int, str, int]], page_chars: List[int], total: int) -> List[dict]:
    entries = sorted(entries, key=lambda e: e[2])
    if not entries:
        return []
    top_level = min(level for level, _, _ in entries)
    groups: List[Tuple[Tuple[int, str, int], List[Tuple[int, str, int]]]] = []
    for entry in entries:
        if entry[0] == top_level or not groups:
            groups.append((entry, []))
        else:
            groups[-1][1].append(entry)
    groups = groups[:MAX_TOP]

    # 第一章之前还有很多页（封面、目录、前言）时补一个"前言"单元，免得漏掉
    chapters = []
    first = groups[0][0][2]
    if first > 3:
        chapters.append(_node("前言与目录", 1, first - 1, page_chars))
    ends = _ranges([g[0][2] for g in groups], total)
    for (head, kids), end in zip(groups, ends):
        node = _node(head[1], head[2], end, page_chars)
        kids = [k for k in kids if head[2] <= k[2] <= end][:MAX_CHILDREN]
        if kids:
            kid_ends = _ranges([k[2] for k in kids], end)
            node["children"] = [_node(k[1], k[2], e, page_chars) for k, e in zip(kids, kid_ends)]
        chapters.append(node)
    return chapters


def page_chunks(page_chars: List[int], total: int) -> List[dict]:
    size = PAGES_PER_CHUNK if total <= PAGES_PER_CHUNK * MAX_TOP else math.ceil(total / MAX_TOP)
    return [_node(f"第 {s}-{min(total, s + size - 1)} 页", s, min(total, s + size - 1), page_chars)
            for s in range(1, total + 1, size)]


# ---------------------------------------------------------------- 模型整理
LLM_PROMPT = """你是学习规划助手。用户上传了一份讲义，下面是从 PDF 中提取的章节（页码范围、字数）与每章开头的文字。
请把它整理成适合复习的单元：太碎的小节合并，太长的章节（超过 120 分钟）拆开，去掉封面、目录、参考文献等不用复习的部分；
标题要简洁清楚（保留"第X章"等编号）。只输出一个 JSON 对象：
{"chapters": [{"title": "第1章 行列式", "pages": [1, 12], "est_minutes": 60,
  "children": [{"title": "1.1 二阶与三阶行列式", "pages": [1, 4], "est_minutes": 20}]}]}
规则：pages 为 [起始页, 结束页]，必须在 1 到总页数之间；est_minutes 按约 150 字/分钟、内容难度估算，10-240 之间；
children 可省略；不要编造讲义里没有的内容。"""


def _validated(items, total: int, depth: int = 1) -> List[dict]:
    result = []
    if not isinstance(items, list):
        return result
    for item in items[: MAX_TOP if depth == 1 else MAX_CHILDREN]:
        if not isinstance(item, dict):
            continue
        title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()[:80]
        pages = item.get("pages")
        try:
            start, end = int(pages[0]), int(pages[1])
            minutes = int(item.get("est_minutes"))
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if not title or not (1 <= start <= end <= total):
            continue
        node = {"title": title, "pages": [start, end], "est_minutes": max(5, min(MAX_MINUTES, minutes))}
        if depth == 1:
            children = _validated(item.get("children"), total, depth=2)
            children = [c for c in children if start <= c["pages"][0] and c["pages"][1] <= end]
            if children:
                node["children"] = children
        result.append(node)
    return result


def llm_outline(config, chapters: List[dict], pages: List[str], total: int, file_name: str) -> List[dict]:
    lines = []
    for chapter in chapters:
        start = chapter["pages"][0]
        preview = re.sub(r"\s+", " ", pages[start - 1] if start - 1 < len(pages) else "")[:120]
        lines.append({"title": chapter["title"], "pages": chapter["pages"], "words": chapter["words"],
                      "children": [c["title"] for c in chapter.get("children", [])], "preview": preview})
    messages = [
        {"role": "system", "content": LLM_PROMPT},
        {"role": "user", "content": f"文件：{file_name}，共 {total} 页。\n章节：\n" + json.dumps(lines, ensure_ascii=False)},
    ]
    data = llm.chat_json(config, messages, temperature=0.2)
    result = _validated(data.get("chapters"), total)
    if not result:
        raise LlmError("模型整理的章节不符合要求")
    # 模型常把小节省略掉：把规则提取到的、页码完全落在该单元内的小节补回去，保留细粒度勾选
    rule_children = [child for chapter in chapters for child in chapter.get("children", [])]
    for node in result:
        if not node.get("children"):
            inside = [dict(c) for c in rule_children
                      if node["pages"][0] <= c["pages"][0] and c["pages"][1] <= node["pages"][1]]
            if len(inside) >= 2:
                node["children"] = inside[:MAX_CHILDREN]
    # 补上字数（模型不给），便于前端显示
    page_chars = [_char_count(text) for text in pages]
    for node in result:
        for item in [node, *node.get("children", [])]:
            item["words"] = sum(page_chars[item["pages"][0] - 1:item["pages"][1]])
    return result


# ---------------------------------------------------------------- 入口
def extract_outline(db: Session, user: User, file_name: str, content: bytes) -> dict:
    if not file_name.lower().endswith(".pdf") and content[:5] != b"%PDF-":
        raise ApiError(415, "仅支持 PDF 文件")
    reader, pages, total = _read_pdf(content)
    page_chars = [_char_count(text) for text in pages] + [0] * (total - len(pages))
    if sum(page_chars) < max(50, min(total, len(pages)) * 10):
        raise ApiError(422, SCANNED_HINT)

    source = "outline"
    entries = _outline_entries(reader, total)
    if not entries:
        source, entries = "headings", _heading_entries(pages)
    chapters = build_tree(entries, page_chars, total) if entries else []
    if not chapters:
        source, chapters = "pages", page_chunks(page_chars, total)

    provider, model, fallback = "rule", None, None
    config = providers.resolve(db, user)
    if config is not None:
        try:
            chapters = llm_outline(config, chapters, pages, total, file_name)
            provider, model = "llm", f"{config.name} · {config.model}"
        except LlmError as error:
            fallback = f"模型整理失败，已按规则提取：{error.message}"

    data = {
        "file_name": file_name,
        "pages": total,
        "words": sum(page_chars),
        "source": source,
        "chapters": chapters,
        "total_minutes": sum(c["est_minutes"] for c in chapters),
        "provider": provider,
        "model": model,
    }
    if fallback:
        data["fallback_reason"] = fallback
    return data
