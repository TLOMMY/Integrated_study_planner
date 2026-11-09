"""
讲义的其他格式：PPT（.pptx）、Word（.docx）、纯文本 / Markdown。测试里直接拼出最小的 Office zip 包，不依赖外部库。
"""

import io
import zipfile

from conftest import body

from app.services import documents

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
P = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
FILLER = "复习这一部分的定义、例题和课后习题，" * 20  # 约 360 字


def zip_bytes(files: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return buffer.getvalue()


def make_docx(paragraphs) -> bytes:
    """paragraphs: [(文字, 样式 id 或 None)]；样式 Heading1 / Heading2 在 styles.xml 里定义。"""
    body_xml = "".join(
        f'<w:p>{f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style else ""}<w:r><w:t>{text}</w:t></w:r></w:p>'
        for text, style in paragraphs
    )
    styles = (f'<w:styles {W}>'
              '<w:style w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>'
              '<w:style w:styleId="Heading2"><w:name w:val="heading 2"/></w:style>'
              '<w:style w:styleId="a3"><w:name w:val="标题 3"/></w:style></w:styles>')
    return zip_bytes({"word/document.xml": f"<w:document {W}><w:body>{body_xml}</w:body></w:document>",
                      "word/styles.xml": styles})


def make_pptx(slides, sections=None) -> bytes:
    """slides: [(标题, [正文行])]；sections: [(节名, 起始幻灯片序号 0 起)]。"""
    ids = [256 + i for i in range(len(slides))]
    sld_list = "".join(f'<p:sldId id="{sid}" r:id="rId{i + 1}"/>' for i, sid in enumerate(ids))
    ext = ""
    if sections:
        bounds = [start for _, start in sections] + [len(slides)]
        items = "".join(
            f'<p14:section name="{name}" id="{{{i}}}"><p14:sldIdLst>'
            + "".join(f'<p14:sldId id="{sid}"/>' for sid in ids[start:bounds[i + 1]])
            + "</p14:sldIdLst></p14:section>"
            for i, (name, start) in enumerate(sections)
        )
        ext = ('<p:extLst><p:ext uri="{521415D9-36F7-43E2-AB2F-B90AF26B5E84}">'
               f'<p14:sectionLst xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main">{items}</p14:sectionLst>'
               "</p:ext></p:extLst>")
    files = {
        "ppt/presentation.xml": f"<p:presentation {P} {R}><p:sldIdLst>{sld_list}</p:sldIdLst>{ext}</p:presentation>",
        "ppt/_rels/presentation.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(f'<Relationship Id="rId{i + 1}" Target="slides/slide{i + 1}.xml"/>' for i in range(len(slides)))
        + "</Relationships>",
    }
    for i, (title, lines) in enumerate(slides):
        shape = lambda text, ph="": (f'<p:sp><p:nvSpPr><p:nvPr>{ph}</p:nvPr></p:nvSpPr><p:txBody>'
                                     f'<a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>')
        shapes = shape(title, '<p:ph type="title"/>') + "".join(shape(line) for line in lines)
        files[f"ppt/slides/slide{i + 1}.xml"] = f"<p:sld {P} {A}><p:cSld><p:spTree>{shapes}</p:spTree></p:cSld></p:sld>"
    return zip_bytes(files)


def upload(client, headers, content, name):
    return client.post("/ai/materials/outline", headers=headers, files={"file": (name, content)})


def test_docx_headings_become_chapters(client, auth):
    content = make_docx([
        ("线性代数讲义", None),
        ("第一章 行列式", "Heading1"), ("1.1 二阶行列式", "Heading2"), (FILLER, None), ("1.2 三阶行列式", "Heading2"), (FILLER, None),
        ("第二章 矩阵", "Heading1"), (FILLER, None), (FILLER, None),
    ])
    data = body(upload(client, auth, content, "线代.docx"))
    assert data["kind"] == "docx" and data["unit"] == "段" and data["source"] == "outline"
    titles = [c["title"] for c in data["chapters"]]
    assert titles == ["第一章 行列式", "第二章 矩阵"]
    assert [c["title"] for c in data["chapters"][0]["children"]] == ["1.1 二阶行列式", "1.2 三阶行列式"]
    assert all(c["est_minutes"] >= 10 for c in data["chapters"])


def test_docx_heading_levels_start_from_heading2(client, auth):
    """只用了"标题 2 / 标题 3"的文档：最高两级仍然当作 章 / 节。"""
    content = make_docx([("第一部分", "Heading2"), ("小节 A", "a3"), (FILLER, None), ("第二部分", "Heading2"), (FILLER, None)])
    data = body(upload(client, auth, content, "notes.docx"))
    assert [c["title"] for c in data["chapters"]] == ["第一部分", "第二部分"]
    assert data["chapters"][0]["children"][0]["title"] == "小节 A"


def test_pptx_sections_and_slide_titles(client, auth):
    slides = [(f"第 {i + 1} 张：知识点", [FILLER[:120]]) for i in range(6)]
    with_sections = make_pptx(slides, sections=[("栈与队列", 0), ("树", 3)])
    data = body(upload(client, auth, with_sections, "数据结构.pptx"))
    assert data["kind"] == "pptx" and data["unit"] == "张" and data["pages"] == 6
    assert [(c["title"], c["pages"]) for c in data["chapters"]] == [("栈与队列", [1, 3]), ("树", [4, 6])]
    # 没有分节、标题写成"第X章"时按正文标题识别
    titled = make_pptx([("第一章 绪论", [FILLER[:120]]), ("内容", [FILLER[:120]]), ("第二章 线性表", [FILLER[:120]]), ("内容", [FILLER[:120]])])
    data = body(upload(client, auth, titled, "ds.pptx"))
    assert data["source"] == "headings" and [c["title"] for c in data["chapters"]] == ["第一章 绪论", "第二章 线性表"]


def test_markdown_and_gbk_text(client, auth):
    md = f"# 第一章 极限\n{FILLER}\n## 1.1 数列极限\n{FILLER}\n# 第二章 导数\n{FILLER}\n".encode("utf-8")
    data = body(upload(client, auth, md, "高数.md"))
    assert data["kind"] == "text" and [c["title"] for c in data["chapters"]] == ["第一章 极限", "第二章 导数"]
    plain = f"第一章 绪论\n{FILLER}\n第二章 方法\n{FILLER}\n".encode("gb18030")
    data = body(upload(client, auth, plain, "笔记.txt"))
    assert [c["title"] for c in data["chapters"]] == ["第一章 绪论", "第二章 方法"]


def test_office_files_are_read_safely():
    # 带外部实体的 XML 不会被展开
    evil = ('<?xml version="1.0"?><!DOCTYPE w [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
            f'<w:document {W}><w:body><w:p><w:r><w:t>&x;第一章 正文</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>正常的一段文字</w:t></w:r></w:p></w:body></w:document>')
    doc = documents.read_docx(zip_bytes({"word/document.xml": evil}))
    text = " ".join(doc.pages)
    assert "root:" not in text and "正常的一段文字" in text
    # 空的 PPT、图片型 PPT 给出明确提示
    import pytest

    from app.core.errors import ApiError

    with pytest.raises(ApiError) as error:
        documents.read_pptx(make_pptx([]))
    assert "没有幻灯片" in error.value.message


def test_image_only_pptx_hint(client, auth):
    response = upload(client, auth, make_pptx([("", []), ("", [])]), "图片课件.pptx")
    assert body(response, 422) is None and "图片" in response.json()["message"]
