"""
图片 / PDF 课表 AI 识别：视觉请求格式、PDF 文字/扫描件两条路径、模型输出校验、
不支持图片的模型提示、提交不再调用模型、用户隔离。所有模型调用均为本地假响应。
"""

import base64
import io
import json

import pytest
from conftest import body
from test_llm import completion, fake_llm, http_error  # noqa: F401 - fake_llm 是夹具

from app.ai import vision


def png_bytes(size=(2400, 1200), mode="RGBA"):
    from PIL import Image, ImageDraw

    image = Image.new(mode, size, (255, 255, 255, 0) if mode == "RGBA" else "white")
    ImageDraw.Draw(image).rectangle([100, 100, 600, 400], outline="black", width=5)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def text_pdf(lines):
    """不依赖 reportlab 的最小文字版 PDF（Helvetica，ASCII 文本）。"""
    stream = "BT /F1 11 Tf 40 760 Td 16 TL " + " ".join(f"({line}) '" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n{obj}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def scanned_pdf():
    from PIL import Image

    buffer = io.BytesIO()
    Image.open(io.BytesIO(png_bytes((800, 600), "RGB"))).save(buffer, format="PDF")
    return buffer.getvalue()


MODEL_REPLY = {
    "courses": [
        {"course_name": "高等数学", "teacher": "王老师", "classroom": "A101", "day_of_week": 1,
         "start_period": 1, "end_period": 2, "week_text": "1-16周", "weeks": [1, 2]},
        {"course_name": "大学英语", "teacher": "", "classroom": "B201", "day_of_week": "周三",
         "start_period": 3, "end_period": 4, "weeks": [2, 4, 6, 8]},
        {"course_name": "高等数学", "teacher": "王老师", "classroom": "A101", "day_of_week": 1,
         "start_period": 1, "end_period": 2, "week_text": "1-16周"},
        {"course_name": "超出节次", "day_of_week": 2, "start_period": 13, "end_period": 14},
        {"course_name": "", "day_of_week": 2, "start_period": 1, "end_period": 2},
        {"course_name": "星期错误", "day_of_week": 9, "start_period": 1, "end_period": 2},
    ],
    "semester_start": "2025-09-01",
}


def _provider(client, headers, model, name="视觉模型"):
    data = body(client.post("/ai/providers", headers=headers, json={
        "name": name, "base_url": "https://m.example.com/v1", "model": model, "api_key": "sk-x"}))
    return next(p["id"] for p in data["providers"] if p["model"] == model)


def _recognize(client, headers, name, content, provider_id=None):
    data = {"provider_id": str(provider_id)} if provider_id is not None else None
    return client.post("/import/timetable/ai", headers=headers, files={"file": (name, content)}, data=data)


def test_image_recognition_preview_and_commit(client, register, fake_llm):  # noqa: F811
    calls, queue = fake_llm
    alice, _ = register()
    _provider(client, alice, "qwen-vl-plus")
    queue.append(completion("识别结果如下：\n```json\n" + json.dumps(MODEL_REPLY, ensure_ascii=False) + "\n```"))

    preview = body(_recognize(client, alice, "课表.png", png_bytes()))
    assert preview["format"] == "ai" and preview["source"] == "image" and preview["model"] == "视觉模型 · qwen-vl-plus"
    assert [c["course_name"] for c in preview["courses"]] == ["高等数学", "大学英语"]  # 重复项去重
    math, english = preview["courses"]
    assert math["weeks"] == list(range(1, 17)) and math["week_text"] == "1-16周"  # 原文周次优先
    assert math["start_time"] == "08:00" and math["color"].startswith("#")
    assert english["day_of_week"] == 3 and english["week_text"] == "2-8周(双)"
    assert {s["name"] for s in preview["skipped"]} == {"超出节次", "第 5 条", "星期错误"}
    assert preview["semester_start"] == "2025-09-01" and preview["total_weeks"] == 20

    sent = calls[-1]["body"]
    assert "response_format" not in sent and sent["temperature"] == 0
    parts = sent["messages"][1]["content"]
    assert parts[0]["type"] == "text" and "共 12 节课" in parts[0]["text"]
    url = parts[1]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    from PIL import Image

    sent_image = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
    assert max(sent_image.size) == vision.MAX_SIDE and sent_image.mode == "RGB"
    assert body(client.get("/timetable", headers=alice))["courses"] == []  # 预览不写库

    # 提交：只交勾选的课程，服务器重新校验，不再调用模型
    before = len(calls)
    committed = body(client.post("/import/timetable/commit", headers=alice, json={
        "courses": [english], "semester_start": preview["semester_start"], "total_weeks": preview["total_weeks"],
        "file_name": preview["file_name"], "fail_count": len(preview["skipped"])}))
    assert len(calls) == before and committed["success_count"] == 1
    assert "importer" in {a["code"] for a in committed["reward"]["new_achievements"]}
    table = body(client.get("/timetable", headers=alice))
    assert [c["course_name"] for c in table["courses"]] == ["大学英语"] and table["semester_start"] == "2025-09-01"
    assert table["courses"][0]["weeks"] == [2, 4, 6, 8]


def test_commit_revalidates_payload(client, auth):
    course = {"course_name": "高等数学", "day_of_week": 1, "start_period": 1, "end_period": 2, "weeks": [1, 2]}
    body(client.post("/import/timetable/commit", headers=auth, json={"courses": []}), 422)
    response = client.post("/import/timetable/commit", headers=auth, json={"courses": [{**course, "end_period": 14}]})
    assert body(response, 422) is None and "超出节次表" in response.json()["message"]
    response = client.post("/import/timetable/commit", headers=auth, json={"courses": [{**course, "weeks": [25]}]})
    assert "周次需在 1-20 周" in response.json()["message"]
    body(client.post("/import/timetable/commit", headers=auth, json={"courses": [course], "semester_start": "2025-13-40"}), 422)
    assert body(client.post("/import/timetable/commit", headers=auth, json={"courses": [course]}))["success_count"] == 1


def test_text_pdf_uses_text_and_any_model(client, auth, fake_llm):  # noqa: F811
    calls, queue = fake_llm
    _provider(client, auth, "deepseek-chat", "DeepSeek")
    pdf = text_pdf(["Course Timetable 2025 Fall", "Period   Monday           Tuesday",
                    "1-2      Advanced Math    Physics", "         Wang A101 1-16   Li B2 2-16 even"])
    queue.append(completion(json.dumps({"courses": [
        {"course_name": "Advanced Math", "teacher": "Wang", "classroom": "A101", "day_of_week": 1,
         "start_period": 1, "end_period": 2, "week_text": "1-16周"},
        {"course_name": "Physics", "teacher": "Li", "classroom": "B2", "day_of_week": 2,
         "start_period": 1, "end_period": 2, "week_text": "2-18周(双)"},
    ]})))
    preview = body(_recognize(client, auth, "kb.pdf", pdf))
    assert preview["source"] == "pdf-text" and preview["success_count"] == 2
    assert preview["total_weeks"] == 20 and preview["courses"][1]["weeks"] == list(range(2, 19, 2))
    sent = calls[-1]["body"]
    assert sent["response_format"] == {"type": "json_object"}
    assert isinstance(sent["messages"][1]["content"], str) and "Advanced Math" in sent["messages"][1]["content"]


def test_scanned_pdf_is_rendered_to_images(client, auth, fake_llm):  # noqa: F811
    calls, queue = fake_llm
    _provider(client, auth, "glm-4v-flash")
    queue.append(completion(json.dumps({"courses": [{"course_name": "线性代数", "day_of_week": 2,
                                                     "start_period": 3, "end_period": 4, "weeks": [1, 2, 3]}]},
                                       ensure_ascii=False)))
    preview = body(_recognize(client, auth, "扫描.pdf", scanned_pdf()))
    assert preview["source"] == "pdf-image" and preview["courses"][0]["week_text"] == "1-3周"
    assert calls[-1]["body"]["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_model_without_vision(client, auth, fake_llm):  # noqa: F811
    calls, queue = fake_llm
    # 已知的纯文本模型：不发请求，直接提示
    text_only = _provider(client, auth, "deepseek-chat", "DeepSeek")
    response = _recognize(client, auth, "kb.jpg", png_bytes((300, 200), "RGB"), text_only)
    assert body(response, 422) is None and "不支持图片识别" in response.json()["message"] and calls == []

    # 未知模型被服务端以 400 拒绝图片：映射为同样的提示
    unknown = _provider(client, auth, "my-local-model", "本地")
    queue.append(http_error(400, "unknown variant `image_url`, expected `text`"))
    response = _recognize(client, auth, "kb.png", png_bytes((300, 200)), unknown)
    assert body(response, 422)["detail"] and "通义千问 qwen-vl" in response.json()["message"]

    # 其他失败（超时/额度）不误报为不支持图片
    vision_model = _provider(client, auth, "gpt-4o", "OpenAI")
    queue.append(http_error(429))
    response = _recognize(client, auth, "kb.png", png_bytes((300, 200)), vision_model)
    assert body(response, 502) is None and "额度" in response.json()["message"]


def test_bad_files_and_provider_choice(client, register, fake_llm):  # noqa: F811
    calls, _ = fake_llm
    alice, _ = register()
    bob, _ = register()
    mine = _provider(client, alice, "qwen-vl-max")
    # 默认 auto 且服务器未配置 DeepSeek：规则引擎无法识别图片
    response = _recognize(client, bob, "kb.png", png_bytes((100, 100)))
    assert body(response, 422) is None and "规则引擎" in response.json()["message"]
    body(_recognize(client, bob, "kb.png", png_bytes((100, 100)), "env"), 422)
    # 不能使用别人的模型配置
    body(_recognize(client, bob, "kb.png", png_bytes((100, 100)), mine), 404)
    body(_recognize(client, alice, "kb.png", png_bytes((100, 100)), "abc"), 422)
    body(_recognize(client, alice, "kb.txt", b"hello world"), 415)
    body(_recognize(client, alice, "kb.pdf", b"%PDF-1.4 broken"), 422)
    assert client.post("/import/timetable/ai", files={"file": ("a.png", b"x")}).status_code == 401
    assert client.post("/import/timetable/commit", json={"courses": []}).status_code == 401
    assert calls == []


def test_parse_model_output_salvages_truncated_json():
    truncated = '{"courses": [{"course_name": "A", "day_of_week": 1, "start_period": 1, "end_period": 2, ' \
                '"weeks": [1, 2]}, {"course_name": "B", "day_of_week": 2, "start_per'
    assert [c["course_name"] for c in vision.parse_model_output(truncated)["courses"]] == ["A"]
    with pytest.raises(Exception, match="没有返回可识别的课表"):
        vision.parse_model_output("抱歉，我看不清这张图片")


def test_merge_weeks_prefers_text_but_keeps_parity():
    assert vision._merge_weeks([1, 2], "1-16周") == list(range(1, 17))
    assert vision._merge_weeks(list(range(2, 17, 2)), "2-16周") == list(range(2, 17, 2))
    assert vision._merge_weeks([2, 4], "2-16周") == list(range(2, 17))
    assert vision._merge_weeks([3, 5], None) == [3, 5]
