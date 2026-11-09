# -*- coding: utf-8 -*-
"""
讲义 / 课件文字读取：PDF、PowerPoint（.pptx）、Word（.docx）、纯文本（.txt / .md）。

统一返回 Doc：
- pages：按"单位"切好的文字（PDF 一页、PPT 一张幻灯片、Word / 文本按标题和字数切成的一段）；
- entries：文件自带的结构 [(层级 1/2, 标题, 起始单位序号 1 起)]，PDF 书签 / PPT 分节 / Word 标题样式 / Markdown 标题；
- unit：前端显示用的单位名（页 / 张 / 段）。

docx / pptx 本质是 zip 里的 XML，这里直接用 zipfile + lxml 读取，不额外安装依赖；
解压时限制每个文件的大小（防压缩炸弹），XML 解析不展开实体、不访问网络。
"""

import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.core.errors import ApiError

MAX_UNITS = 800
MAX_XML_BYTES = 30 * 1024 * 1024
SEGMENT_CHARS = 1200  # Word / 文本：一段约 1200 字（8 分钟左右的阅读量）

SUPPORTED = ".pdf / .pptx / .docx / .txt / .md"
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "p14": "http://schemas.microsoft.com/office/powerpoint/2010/main",
}


@dataclass
class Doc:
    kind: str  # pdf / pptx / docx / text
    unit: str  # 页 / 张 / 段
    pages: List[str]
    total: int
    entries: List[Tuple[int, str, int]] = field(default_factory=list)
    reader: object = None  # PDF 时是 PdfReader（读书签用）


def kind_of(file_name: str, content: bytes) -> Optional[str]:
    name = (file_name or "").lower()
    if content[:5] == b"%PDF-":
        return "pdf"
    if name.endswith(".pptx"):
        return "pptx"
    if name.endswith(".docx"):
        return "docx"
    if name.endswith((".txt", ".md", ".markdown")):
        return "text"
    return None


# ---------------------------------------------------------------- 工具
def _xml(zf: zipfile.ZipFile, name: str):
    from lxml import etree

    try:
        info = zf.getinfo(name)
    except KeyError:
        return None
    if info.file_size > MAX_XML_BYTES:
        raise ApiError(422, "文件内容太大，无法读取")
    with zf.open(info) as fh:
        data = fh.read(MAX_XML_BYTES + 1)
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, recover=True)
    return etree.fromstring(data, parser)


def _open_zip(content: bytes) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, ValueError):
        raise ApiError(422, "文件已损坏或不是有效的 Office 文件（旧版 .doc / .ppt 请先另存为 .docx / .pptx）") from None


def _clean(text: str) -> str:
    return re.sub(r"[ \t　]+", " ", text or "").strip()


def paginate(blocks: List[Tuple[str, Optional[int]]]) -> Tuple[List[str], List[Tuple[int, str, int]]]:
    """
    把 [(文字, 标题层级或 None)] 切成若干段：遇到一级标题或累计约 SEGMENT_CHARS 字时换段。
    返回 (各段文字, 标题条目)。
    """
    pages: List[str] = []
    entries: List[Tuple[int, str, int]] = []
    current: List[str] = []
    size = 0
    for text, level in blocks:
        text = _clean(text)
        if not text:
            continue
        if current and (level == 1 or size >= SEGMENT_CHARS):
            pages.append("\n".join(current))
            current, size = [], 0
        if level in (1, 2):
            entries.append((level, text[:80], len(pages) + 1))
        current.append(text)
        size += len(text)
        if len(pages) >= MAX_UNITS:
            break
    if current and len(pages) < MAX_UNITS:
        pages.append("\n".join(current))
    return pages, entries


# ---------------------------------------------------------------- PDF
def read_pdf(content: bytes) -> Doc:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ApiError(422, "PDF 已加密，请先解除密码再上传")
        pages = []
        for page in reader.pages[:MAX_UNITS]:
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
    return Doc("pdf", "页", pages, total, reader=reader)
# ---------------------------------------------------------------- PowerPoint
def read_pptx(content: bytes) -> Doc:
    zf = _open_zip(content)
    pres = _xml(zf, "ppt/presentation.xml")
    rels = _xml(zf, "ppt/_rels/presentation.xml.rels")
    if pres is None or rels is None:
        raise ApiError(422, "不是有效的 PowerPoint 文件（.pptx）")
    targets = {r.get("Id"): r.get("Target") for r in rels.findall("rel:Relationship", NS)}
    slide_ids = []  # (幻灯片 id, 文件路径)
    for sld in pres.findall("p:sldIdLst/p:sldId", NS):
        target = targets.get(sld.get(f"{{{NS['r']}}}id"))
        if target:
            slide_ids.append((sld.get("id"), "ppt/" + target.lstrip("/").removeprefix("ppt/")))
    slide_ids = slide_ids[:MAX_UNITS]

    pages = []
    for _, path in slide_ids:
        root = _xml(zf, path)
        if root is None:
            pages.append("")
            continue
        title, lines = "", []
        for shape in root.iter(f"{{{NS['p']}}}sp"):
            ph = shape.find("p:nvSpPr/p:nvPr/p:ph", NS)
            paras = ["".join(t.text or "" for t in para.iter(f"{{{NS['a']}}}t")) for para in shape.iter(f"{{{NS['a']}}}p")]
            paras = [_clean(p) for p in paras if _clean(p)]
            if ph is not None and ph.get("type") in ("title", "ctrTitle") and not title:
                title = " ".join(paras)
            else:
                lines += paras
        # 标题放第一行，正文标题识别（"第一章 …"）能直接认出来
        pages.append("\n".join([title, *lines] if title else lines))

    # PowerPoint 的"节"（2010+）：作为一级结构
    entries = []
    position = {sid: index for index, (sid, _) in enumerate(slide_ids, start=1)}
    for section in pres.iter(f"{{{NS['p14']}}}section"):
        first = next((s.get("id") for s in section.iter(f"{{{NS['p14']}}}sldId") if s.get("id") in position), None)
        name = _clean(section.get("name") or "")
        if first and name:
            entries.append((1, name[:80], position[first]))
    if len(entries) < 2:
        entries = []
    if not pages:
        raise ApiError(422, "PPT 里没有幻灯片")
    return Doc("pptx", "张", pages, len(pages), entries)


# ---------------------------------------------------------------- Word
_HEADING_NAME = re.compile(r"^(?:heading|标题)\s*(\d)$", re.I)


def _normalize_levels(blocks: List[Tuple[str, Optional[int]]]) -> List[Tuple[str, Optional[int]]]:
    """文档里实际用到的最高两级标题分别当作 章 / 节（很多人从"标题 2"开始用）。"""
    used = sorted({level for _, level in blocks if level})
    mapping = {level: index for index, level in enumerate(used[:2], start=1)}
    return [(text, mapping.get(level)) for text, level in blocks]


def read_docx(content: bytes) -> Doc:
    zf = _open_zip(content)
    document = _xml(zf, "word/document.xml")
    if document is None:
        raise ApiError(422, "不是有效的 Word 文件（.docx）")
    w = f"{{{NS['w']}}}"
    styles = {}
    styles_root = _xml(zf, "word/styles.xml")
    if styles_root is not None:
        for style in styles_root.findall("w:style", NS):
            name = style.find("w:name", NS)
            outline = style.find("w:pPr/w:outlineLvl", NS)
            level = None
            if outline is not None and (outline.get(f"{w}val") or "").isdigit():
                level = int(outline.get(f"{w}val")) + 1
            elif name is not None and (match := _HEADING_NAME.match(name.get(f"{w}val") or "")):
                level = int(match.group(1))
            styles[style.get(f"{w}styleId")] = level

    blocks = []
    body_el = document.find("w:body", NS)
    for para in (body_el.iter(f"{w}p") if body_el is not None else []):
        text = "".join(t.text or "" for t in para.iter(f"{w}t"))
        if not text.strip():
            continue
        level = None
        own = para.find("w:pPr/w:outlineLvl", NS)
        style = para.find("w:pPr/w:pStyle", NS)
        if own is not None and (own.get(f"{w}val") or "").isdigit():
            level = int(own.get(f"{w}val")) + 1
        elif style is not None:
            level = styles.get(style.get(f"{w}val"))
        blocks.append((text, level if level and level <= 9 else None))
    pages, entries = paginate(_normalize_levels(blocks))
    if not pages:
        raise ApiError(422, "Word 文件里没有文字")
    return Doc("docx", "段", pages, len(pages), entries)


# ---------------------------------------------------------------- 纯文本 / Markdown
def read_text(content: bytes, heading_level) -> Doc:
    """heading_level(line) -> 1 / 2 / None：识别"第一章 …""1.2 …"这类标题（由调用方提供规则）。"""
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ApiError(422, "文本文件的编码无法识别，请另存为 UTF-8")
    blocks = []
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            blocks.append((match.group(2), len(match.group(1))))
        else:
            clean = _clean(line)
            blocks.append((clean, heading_level(clean) if clean else None))
    pages, entries = paginate(_normalize_levels(blocks))
    if not pages:
        raise ApiError(422, "文件里没有文字")
    return Doc("text", "段", pages, len(pages), entries)


def read(file_name: str, content: bytes, heading_level) -> Doc:
    kind = kind_of(file_name, content)
    if kind == "pdf":
        return read_pdf(content)
    if kind == "pptx":
        return read_pptx(content)
    if kind == "docx":
        return read_docx(content)
    if kind == "text":
        return read_text(content, heading_level)
    raise ApiError(415, f"支持 {SUPPORTED}（旧版 .doc / .ppt 请先另存为新格式）")
