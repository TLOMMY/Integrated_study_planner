"""
PDF 讲义提取章节：书签 → 章节树、正文标题识别、按页分段、扫描件提示、文件校验、模型整理与校验回退。
PDF 用 pypdf 现场生成（带真实文字层与书签）；模型调用被替换为本地假响应。
"""

import io
import json

import pytest
from conftest import body
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.ai import llm
from app.services import materials


def make_pdf(pages, outline=None) -> bytes:
    """pages: 每页的文字行列表；outline: [(标题, 页码 0 起, [(子标题, 页码)])]。"""
    writer = PdfWriter()
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    for lines in pages:
        page = writer.add_blank_page(width=595, height=842)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})})
        ops = ["BT", "/F1 11 Tf", "14 TL", "50 800 Td"]
        for line in lines:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"({safe}) Tj T*")
        ops.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(ops).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    for title, index, children in outline or []:
        parent = writer.add_outline_item(title, index)
        for child_title, child_index in children:
            writer.add_outline_item(child_title, child_index, parent=parent)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def text_page(prefix: str, lines: int = 30):
    return [f"{prefix} line {i} matrix determinant eigenvalue vector space basis" for i in range(lines)]


def upload(client, headers, content: bytes, name: str = "lecture.pdf"):
    return client.post("/ai/materials/outline", headers=headers,
                       files={"file": (name, content, "application/pdf")})


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
        return FakeResponse(queue.pop(0))

    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)
    return calls, queue


def completion(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


# ---------------------------------------------------------------- 规则提取
def test_outline_tree_with_page_ranges(client, auth):
    pages = [text_page(f"p{i}") for i in range(12)]
    pdf = make_pdf(pages, outline=[
        ("第1章 行列式", 0, [("1.1 二阶行列式", 0), ("1.2 性质", 2)]),
        ("第2章 矩阵", 5, []),
        ("第3章 线性方程组", 9, []),
    ])
    data = body(upload(client, auth, pdf))
    assert data["file_name"] == "lecture.pdf" and data["pages"] == 12
    assert data["source"] == "outline" and data["provider"] == "rule"
    chapters = data["chapters"]
    assert [c["title"] for c in chapters] == ["第1章 行列式", "第2章 矩阵", "第3章 线性方程组"]
    assert [c["pages"] for c in chapters] == [[1, 5], [6, 9], [10, 12]]
    assert [c["pages"] for c in chapters[0]["children"]] == [[1, 2], [3, 5]]
    assert "children" not in chapters[1]
    assert all(c["words"] > 0 and materials.MIN_MINUTES <= c["est_minutes"] <= materials.MAX_MINUTES
               for c in chapters)
    assert data["total_minutes"] == sum(c["est_minutes"] for c in chapters)


def test_headings_detected_without_outline(client, auth):
    pages = [["Chapter 1 Determinants", *text_page("a")], text_page("b"),
             ["Chapter 2 Matrices", *text_page("c")], ["Chapter 2 Matrices", *text_page("d")],  # 页眉重复
             ["2.1 Inverse matrix", *text_page("e")]]
    data = body(upload(client, auth, make_pdf(pages)))
    assert data["source"] == "headings"
    assert [(c["title"], c["pages"]) for c in data["chapters"]] == [
        ("Chapter 1 Determinants", [1, 2]), ("Chapter 2 Matrices", [3, 5])]
    assert data["chapters"][1]["children"] == [
        {**data["chapters"][1]["children"][0], "title": "2.1 Inverse matrix", "pages": [5, 5]}]


def test_plain_text_falls_back_to_page_chunks(client, auth):
    data = body(upload(client, auth, make_pdf([text_page(f"x{i}", 10) for i in range(23)])))
    assert data["source"] == "pages"
    assert [c["pages"] for c in data["chapters"]] == [[1, 10], [11, 20], [21, 23]]
    assert data["chapters"][0]["title"] == "第 1-10 页"


def test_invalid_files(client, auth):
    # 扫描件（没有文字层）
    response = upload(client, auth, make_pdf([[], [], []]))
    assert body(response, 422) is None and "扫描件" in response.json()["message"]
    # 不是 PDF
    response = upload(client, auth, b"PK\x03\x04 not a pdf", "notes.docx")
    assert body(response, 415) is None and "PDF" in response.json()["message"]
    # 损坏的 PDF
    body(upload(client, auth, b"%PDF-1.7 garbage"), 422)
    # 空文件、超过大小
    body(upload(client, auth, b""), 422)
    body(upload(client, auth, b"%PDF-" + b"0" * (5 * 1024 * 1024 + 10)), 413)


# ---------------------------------------------------------------- 模型整理
def test_llm_reorganizes_and_is_validated(client, register, fake_llm):
    calls, queue = fake_llm
    headers, _ = register()
    body(client.post("/ai/providers", headers=headers, json={
        "name": "测试模型", "base_url": "https://m.example.com/v1", "model": "m1", "api_key": "sk-x"}))
    pdf = make_pdf([text_page(f"p{i}") for i in range(8)],
                   outline=[("Ch1", 0, []), ("Ch2", 3, []), ("References", 7, [])])

    queue.append(completion(json.dumps({"chapters": [
        {"title": "第1章 基础", "pages": [1, 3], "est_minutes": 40,
         "children": [{"title": "1.1", "pages": [1, 2], "est_minutes": 20},
                      {"title": "越界小节", "pages": [2, 6], "est_minutes": 20}]},
        {"title": "第2章 进阶", "pages": [4, 7], "est_minutes": 999},
        {"title": "页码越界", "pages": [5, 30], "est_minutes": 30},
        {"title": "", "pages": [1, 1], "est_minutes": 10},
    ]}, ensure_ascii=False)))
    data = body(upload(client, headers, pdf))
    assert data["provider"] == "llm" and data["model"] == "测试模型 · m1"
    assert [c["title"] for c in data["chapters"]] == ["第1章 基础", "第2章 进阶"]
    assert [c["title"] for c in data["chapters"][0]["children"]] == ["1.1"]
    assert data["chapters"][1]["est_minutes"] == materials.MAX_MINUTES
    assert data["chapters"][0]["words"] > 0
    sent = calls[0]["messages"][1]["content"]
    assert "共 8 页" in sent and "References" in sent

    # 模型返回的章节全部不合格 → 回退规则结果并说明
    queue.append(completion('{"chapters": [{"title": "x", "pages": [0, 99], "est_minutes": 5}]}'))
    data = body(upload(client, headers, pdf))
    assert data["provider"] == "rule" and data["source"] == "outline" and "fallback_reason" in data
    assert [c["title"] for c in data["chapters"]] == ["Ch1", "Ch2", "References"]


def test_llm_units_keep_rule_subsections(client, register, fake_llm):
    _, queue = fake_llm
    headers, _ = register()
    body(client.post("/ai/providers", headers=headers, json={
        "name": "测试模型", "base_url": "https://m.example.com/v1", "model": "m1", "api_key": "sk-x"}))
    pdf = make_pdf([text_page(f"p{i}") for i in range(10)],
                   outline=[("Ch1", 0, [("1.1", 0), ("1.2", 2)]), ("Ch2", 5, [("2.1", 5), ("2.2", 7)])])
    # 模型把两章合成一个单元、且没给小节：补回页码落在单元内的全部规则小节
    queue.append(completion('{"chapters": [{"title": "全书", "pages": [1, 10], "est_minutes": 120}]}'))
    data = body(upload(client, headers, pdf))
    assert data["provider"] == "llm"
    assert [c["title"] for c in data["chapters"][0]["children"]] == ["1.1", "1.2", "2.1", "2.2"]
