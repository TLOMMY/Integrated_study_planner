# -*- coding: utf-8 -*-
"""
教务网页课表解析（对标 WakeUp 的"从教务系统导入"）。

网页应用无法跨域读取学校教务系统的页面，所以由用户把课表页交给我们：
  · 浏览器 Ctrl+S 保存的 .html / .htm / .mhtml（单个文件，含 iframe 里的课表）
  · 复制的页面源代码，或书签小工具复制的内容（多个 frame 用 FRAME_MARKER 拼接）
  · 正方新版接口返回的 JSON（含 kbList）

支持的版式：
  · 正方旧版 #Table1 / 强智 #kbtable（kbcontent）/ 青果 / 通用表格：找到含"星期一…星期日"表头的 <table>，
    展开 rowspan / colspan 后得到与 Excel 相同的二维单元格，再按课程块解析；
  · 正方新版 #kbgrid_table_0（td#1-1 内的 div.timetable_con）同样按表格解析；
  · 正方新版 JSON：kbList[].kcmc / xm / cdmc / xqj / jcs / zcd。

输入不可信：只做静态解析（lxml 不执行脚本），先去掉 script/style 等节点，限制体积、表格数量和合并单元格跨度。
"""

import email
import email.policy
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.errors import ApiError
from app.services import import_common, schedule
from app.services.importer import (
    ParseResult,
    _detect_meta,
    _find_day_header,
    _parse_cell,
    clean_classroom,
    clean_teacher,
    group_lines,
    label_for,
    parse_blocks,
    row_periods,
)

SUPPORTED_SUFFIXES = {".html", ".htm", ".mhtml", ".mht", ".json", ".txt", ""}
FRAME_MARKER = "<!--STUDY-PLANNER-FRAME-->"
MAX_TABLES = 80
MAX_SPAN = 24
MAX_KB_ITEMS = 500

_BLOCK_TAGS = {"br", "p", "div", "tr", "td", "th", "table", "li", "ul", "ol", "hr", "h1", "h2", "h3", "h4", "h5",
               "h6", "section", "article", "dd", "dt", "dl"}
_DROP_TAGS = ("script", "style", "noscript", "template", "iframe", "frame", "object", "embed", "svg", "head", "link",
              "meta", "button", "input", "textarea")
_COURSE_DIV = re.compile(r"\b(?:timetable_con|kbcontent)\b")


# ---------------------------------------------------------------- 解码
def _decode(content: bytes, hint: Optional[str] = None) -> str:
    if content.startswith(b"\xef\xbb\xbf"):
        return content[3:].decode("utf-8", "replace")
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return content.decode("utf-16", "replace")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    declared = re.search(rb"<meta[^>]+charset=[\"']?\s*([A-Za-z0-9_\-]+)", content[:4096], re.I)
    candidates = [hint, declared.group(1).decode("ascii", "ignore") if declared else None, "gb18030"]
    for encoding in candidates:
        if not encoding:
            continue
        encoding = encoding.lower()
        if encoding in ("gbk", "gb2312", "gb_2312-80", "x-gbk"):
            encoding = "gb18030"
        try:
            return content.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode("utf-8", "replace")


def _is_mhtml(filename: str, content: bytes) -> bool:
    if Path(filename or "").suffix.lower() in (".mhtml", ".mht"):
        return True
    head = content[:4096].lower()
    return b"mime-version" in head and b"multipart/related" in head


def _mhtml_documents(content: bytes) -> List[str]:
    """取出 .mhtml 里所有 text/html 部分（Chrome 会把 iframe 的页面也存成单独部分）。"""
    try:
        message = email.message_from_bytes(content, policy=email.policy.compat32)
    except Exception:  # noqa: BLE001 - 损坏的 MIME 结构
        raise ApiError(422, "MHTML 文件无法解析，请重新保存网页")
    documents = []
    for part in message.walk():
        if part.get_content_type() != "text/html":
            continue
        payload = part.get_payload(decode=True)
        if payload:
            documents.append(_decode(payload, part.get_content_charset()))
    if not documents:
        raise ApiError(422, "MHTML 文件里没有找到网页内容")
    return documents


# ---------------------------------------------------------------- HTML 结构
def _parse_html(text: str):
    """静态解析 HTML（不执行脚本、不访问网络），并删除脚本、样式、表单控件等无关节点。"""
    from lxml import etree, html

    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text)
    parser = html.HTMLParser(remove_comments=True, remove_pis=True, no_network=True)
    try:
        root = html.document_fromstring(text, parser=parser)
    except (etree.ParserError, ValueError):
        return None
    flags = {
        "frame": any(True for _ in root.iter("iframe", "frame", "frameset")),
        "password": any((node.get("type") or "").lower() == "password" for node in root.iter("input")),
    }
    for node in [n for n in root.iter(*_DROP_TAGS)]:
        if node.getparent() is not None:
            node.drop_tree()
    return root, flags


def _cell_lines(cell) -> List[Tuple[Optional[str], Optional[str]]]:
    """
    把一个 <td> 拆成 (文本, 标签) 行；文本为 None 表示课程分隔，"" 表示连续 <br> 形成的空行。
    标签来自 title 属性（强智 <font title='老师'>、正方新版 <span title='上课地点'>）或 span.title（课程名）。
    """
    containers = [div for div in cell.iter("div") if "kbcontent" in (div.get("class") or "").split()]
    lines: List[Tuple[Optional[str], Optional[str]]] = []
    buffer: List[str] = []
    state = {"label": None, "pending": None, "br": False}

    def add(text: str, label: Optional[str]):
        if not text:
            return
        if text.strip():
            if not "".join(buffer).strip():
                state["label"] = label or state["pending"]
                state["pending"] = None
            state["br"] = False
        buffer.append(text)

    def flush():
        text = re.sub(r"[ 	 　]+", " ", "".join(buffer)).strip()
        buffer.clear()
        if text:
            lines.append((text, state["label"]))
        state["label"] = None

    def walk(node, label):
        tag = node.tag if isinstance(node.tag, str) else ""
        classes = (node.get("class") or "").split()
        own = "name" if tag == "span" and "title" in classes else label_for(node.get("title") or "")
        if tag == "br":
            if state["br"] and not "".join(buffer).strip():
                lines.append(("", None))
            flush()
            state["br"] = True
            return
        if tag in _BLOCK_TAGS:
            flush()
            state["br"] = False
            if tag == "hr" or (tag == "div" and _COURSE_DIV.search(" ".join(classes)) and lines):
                lines.append((None, None))
        current = own or label
        if own and not node.text_content().strip():
            # 只有图标没有文字的 <span title='上课地点'>，标签作用到紧随其后的文字
            state["pending"] = own
        add(node.text or "", current)
        for child in node:
            walk(child, current)
            add(child.tail or "", current)
        if tag in _BLOCK_TAGS or (own and node.text_content().strip()):
            flush()

    for root in containers or [cell]:
        walk(root, None)
        flush()
        lines.append((None, None))
    return lines


def _cell_text(lines) -> str:
    return "\n".join(text for text, _ in lines if text)


def _span_attr(node, name: str) -> int:
    try:
        return max(1, min(MAX_SPAN, int(str(node.get(name) or "1").strip() or 1)))
    except ValueError:
        return 1


def _table_grid(table):
    """
    展开 rowspan/colspan。返回 (texts, origins)：
      texts[r][c]   每个格子的文字（合并区域内每格都填，用于找表头和行首节次）；
      origins[r][c] 只在合并区域左上角放 (rowspan, lines)，避免同一门课被重复解析。
    只取本表自己的行（./tr、./tbody/tr），嵌套表格单独作为候选。
    """
    rows = table.xpath("./tr | ./thead/tr | ./tbody/tr | ./tfoot/tr")[:200]
    texts: Dict[Tuple[int, int], str] = {}
    origins: Dict[Tuple[int, int], tuple] = {}
    for r, row in enumerate(rows):
        c = 0
        for cell in row.xpath("./td | ./th")[:40]:
            while (r, c) in texts:
                c += 1
            lines = _cell_lines(cell)
            text = _cell_text(lines)
            rowspan, colspan = _span_attr(cell, "rowspan"), _span_attr(cell, "colspan")
            for dr in range(rowspan):
                for dc in range(colspan):
                    texts[(r + dr, c + dc)] = text
            origins[(r, c)] = (rowspan, lines)
            c += colspan
    height = len(rows)
    width = max((col for _, col in texts), default=-1) + 1
    grid = [[texts.get((r, c), "") for c in range(width)] for r in range(height)]
    return grid, origins


def _span_periods(grid, row_index: int, rowspan: int, first_day: int):
    """合并单元格的节次：首行的起始节 ~ 末行的结束节。"""
    start = row_periods(grid[row_index][:first_day])
    last = min(len(grid) - 1, row_index + rowspan - 1)
    end = row_periods(grid[last][:first_day]) if last != row_index else start
    if start and end:
        return start[0], max(start[1], end[1])
    return start or end


def _parse_table(table, default_total: int) -> Optional[ParseResult]:
    grid, origins = _table_grid(table)
    header_index, day_columns = _find_day_header(grid, max_rows=15, first_line=True)
    if header_index is None:
        return None
    result = ParseResult(format="web")
    seen: set = set()
    first_day = min(day_columns)
    for r in range(header_index + 1, len(grid)):
        for col, day in day_columns.items():
            info = origins.get((r, col))
            if not info:
                continue
            rowspan, lines = info
            text = _cell_text(lines)
            if not text:
                continue
            fallback = _span_periods(grid, r, rowspan, first_day)
            if "◇" in text:
                _parse_cell(text, day, 30, result, seen, fallback, default_total)
            else:
                parse_blocks(group_lines(lines), day, fallback, 30, default_total, result, seen)
    return result


def _selected_semester(root) -> Optional[str]:
    """学年/学期下拉框里被选中的项：学年 "2025-2026"，学期 1/2（正方新版 xqm=3/12/16 表示第 1/2/3 学期）。"""
    year, term = None, None
    for select in root.iter("select"):
        name = (select.get("name") or select.get("id") or "").lower()
        option = next((o for o in select.iter("option") if o.get("selected") is not None), None)
        if option is None or name.startswith("xqj"):
            continue
        value = (option.get("value") or "").strip()
        label = option.text_content().strip()
        if m := re.search(r"(\d{4})-(\d{4})", label or value):
            year = f"{m.group(1)}-{m.group(2)}"
        elif name.startswith("xn") and re.fullmatch(r"\d{4}", value):
            year = f"{value}-{int(value) + 1}"
        elif name.startswith("xq") or "学期" in label:
            term = {"3": "1", "12": "2", "16": "3", "一": "1", "二": "2", "三": "3"}.get(value or label, value or label)
    return f"{year}-{term}" if year and term in ("1", "2", "3") else None


def _parse_documents(documents: List[str], user) -> ParseResult:
    default_total = int(user.total_weeks or 20)
    best: Optional[ParseResult] = None
    semester: Optional[str] = None
    meta_lines: List[List[str]] = []
    has_frame = has_password = saw_grid = False
    for text in documents:
        stripped = text.strip()
        if stripped.startswith(("{", "[")):
            try:
                return _parse_kb_json(json.loads(stripped), user)
            except ValueError:
                pass
        parsed_html = _parse_html(text)
        if parsed_html is None:
            continue
        root, flags = parsed_html
        has_frame |= flags["frame"]
        has_password |= flags["password"]
        semester = semester or _selected_semester(root)
        for select in list(root.iter("select")):
            select.drop_tree()
        body_text = root.text_content().strip()
        # 浏览器直接打开接口地址再保存时，JSON 在 <pre> 里
        if body_text.startswith("{") and "kbList" in body_text:
            try:
                return _parse_kb_json(json.loads(body_text), user)
            except ValueError:
                pass
        meta_lines.append([line.strip() for line in body_text.split("\n") if line.strip()][:400])
        for table in list(root.iter("table"))[:MAX_TABLES]:
            parsed = _parse_table(table, default_total)
            if parsed is None:
                continue
            saw_grid = True
            if best is None or len(parsed.courses) > len(best.courses):
                best = parsed

    if best is None or not best.courses:
        if saw_grid:
            raise ApiError(422, "找到了课表表格但里面没有课程：请确认已选择正确的学年学期并点过“查询”，再保存页面",
                           {"skipped": best.skipped if best else []})
        if has_password:
            raise ApiError(422, "这是登录页面：请先在教务系统登录，打开“我的课表/学生课表”页面后再保存")
        if has_frame:
            raise ApiError(422, "课表在页面的内嵌框架里：请用“网页，单个文件（.mhtml）”保存，或用书签小工具复制")
        raise ApiError(422, "没有在网页里找到课表：需要包含“星期一…星期日”表头的课表页面（不是首页或成绩页）")

    _detect_meta(meta_lines, best)
    best.semester = best.semester or semester
    return best


# ---------------------------------------------------------------- 正方新版 JSON
def _find_key(value, key: str, depth: int = 0):
    if depth > 4:
        return None
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = _find_key(child, key, depth + 1)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value[:20]:
            found = _find_key(child, key, depth + 1)
            if found is not None:
                return found
    return None


def _parse_kb_json(data, user) -> ParseResult:
    items = _find_key(data, "kbList")
    if not isinstance(items, list):
        raise ApiError(422, "JSON 里没有找到 kbList：请粘贴正方教务“学生课表查询”接口返回的完整内容")
    result = ParseResult(format="zf-json")
    default_total = int(user.total_weeks or 20)
    seen: set = set()
    for item in items[:MAX_KB_ITEMS]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("kcmc") or "").strip()
        if not name:
            continue
        day = import_common.parse_day(item.get("xqj") or item.get("xqjmc"))
        periods = re.findall(r"\d+", str(item.get("jcs") or item.get("jc") or item.get("jcor") or ""))
        if day is None or not periods:
            result.skipped.append({"name": name[:60], "reason": "缺少星期或节次"})
            continue
        p1, p2 = min(int(p) for p in periods), max(int(p) for p in periods)
        week_text = str(item.get("zcd") or "").strip()
        weeks = schedule.parse_week_text(week_text, 30) if week_text else list(range(1, default_total + 1))
        if not weeks:
            result.skipped.append({"name": name[:60], "reason": f"周次无法识别：{week_text[:30]}"})
            continue
        key = (name, day, p1, p2, tuple(weeks))
        if key in seen:
            continue
        seen.add(key)
        result.courses.append({
            "course_name": name[:160], "day_of_week": day, "start_period": p1, "end_period": p2,
            "weeks": weeks, "week_text": schedule.format_weeks(weeks),
            "teacher": clean_teacher(str(item.get("xm") or "")),
            "classroom": clean_classroom(str(item.get("cdmc") or "")),
        })
    for item in (_find_key(data, "sjkList") or [])[:100]:
        if isinstance(item, dict):
            name = str(item.get("kcmc") or item.get("sjkcgs") or item.get("qtkcgs") or "").strip()
            if name:
                result.skipped.append({"name": name[:60], "reason": "实践课/其他课程没有固定上课时间"})
    info = _find_key(data, "xsxx")
    if isinstance(info, dict):
        year = str(info.get("XNMC") or info.get("xnmc") or "")
        term = str(info.get("XQMMC") or info.get("xqmmc") or info.get("XQMM") or "")
        term = {"3": "1", "12": "2", "16": "3"}.get(term, term)
        if re.fullmatch(r"\d{4}-\d{4}", year) and term in ("1", "2", "3"):
            result.semester = f"{year}-{term}"
    return result


# ---------------------------------------------------------------- 入口
def parse_web_timetable(filename: str, content: bytes, user) -> ParseResult:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ApiError(415, "请上传浏览器保存的课表网页（.html / .mhtml），或直接粘贴页面源代码")
    if _is_mhtml(filename, content):
        documents = _mhtml_documents(content)
    else:
        text = _decode(content)
        if "<" not in text and not text.lstrip().startswith(("{", "[")):
            raise ApiError(422, "内容不是网页源代码或 JSON：请在课表页按 Ctrl+U 查看源代码后全选复制")
        documents = [part for part in text.split(FRAME_MARKER) if part.strip()]
    if not documents:
        raise ApiError(422, "内容为空")

    result = _parse_documents(documents, user)
    if not result.courses:
        raise ApiError(422, "网页里没有解析出任何课程", {"skipped": result.skipped})
    # 网页通常不写总周数：课程周次超过当前设置时自动放宽（例如 1-18 周）
    if not result.total_weeks:
        widened = import_common.widen_total_weeks(result.courses, int(user.total_weeks or 20))
        if widened != int(user.total_weeks or 20):
            result.total_weeks = widened
    return result
