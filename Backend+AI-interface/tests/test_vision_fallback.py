"""
服务器视觉模型（火山方舟 · 豆包）：所选模型不能看图时，课表图片 / 扫描版 PDF 交给它；
文字版 PDF 也渲染成图片一起给它（只看文字时容易认错节次和单双周）。模型调用都是本地假响应。
"""

import json

import pytest
from conftest import body
from test_import_ai import _provider, _recognize, png_bytes, text_pdf
from test_llm import completion, fake_llm  # noqa: F401 - fake_llm 是夹具

from app.core.config import settings

REPLY = json.dumps({"courses": [{"course_name": "高等数学", "day_of_week": 1, "start_period": 1, "end_period": 2,
                                 "week_text": "1-16周(单)"}]}, ensure_ascii=False)


@pytest.fixture
def ark(monkeypatch):
    monkeypatch.setattr(settings, "ARK_API_KEY", "ark-test-key")
    monkeypatch.setattr(settings, "ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    monkeypatch.setattr(settings, "ARK_MODEL", "doubao-seed-test")


def test_image_goes_to_ark_when_active_model_is_text_only(client, register, fake_llm, ark):  # noqa: F811
    calls, queue = fake_llm
    headers, _ = register()
    _provider(client, headers, "deepseek-chat", name="我的 DeepSeek")  # 不能看图
    queue.append(completion(REPLY))
    preview = body(_recognize(client, headers, "课表.png", png_bytes()))
    sent = calls[-1]
    assert sent["url"] == "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    assert sent["body"]["model"] == "doubao-seed-test"
    assert sent["body"]["thinking"] == {"type": "disabled"}, "抽取类调用关闭深度思考"
    assert any(part.get("type") == "image_url" for part in sent["body"]["messages"][1]["content"])
    # "1-16周(单)"的最后一周是 15，规范化成 1-15 周单周
    assert preview["model"].startswith("豆包") and preview["courses"][0]["weeks"] == list(range(1, 16, 2))


def test_text_pdf_also_sends_page_image_to_ark(client, register, fake_llm, ark):  # noqa: F811
    calls, queue = fake_llm
    headers, _ = register()
    _provider(client, headers, "deepseek-chat", name="我的 DeepSeek")
    queue.append(completion(REPLY))
    pdf = text_pdf(["Monday Tuesday Wednesday", "1-2 Course Advanced Math 1-16 odd weeks", "3-4 Course English"])
    preview = body(_recognize(client, headers, "kb.pdf", pdf))
    content = calls[-1]["body"]["messages"][1]["content"]
    assert content[0]["type"] == "text" and "以图片为准" in content[0]["text"] and "Advanced Math" in content[0]["text"]
    assert any(part.get("type") == "image_url" for part in content)
    assert preview["source"] == "pdf-text+image"


def test_explicit_provider_choice_is_respected(client, register, fake_llm, ark):  # noqa: F811
    calls, _ = fake_llm
    headers, _ = register()
    provider_id = _provider(client, headers, "deepseek-chat", name="我的 DeepSeek")
    response = _recognize(client, headers, "课表.png", png_bytes(), provider_id=provider_id)
    assert body(response, 422)["reason"] == "no_vision"
    assert calls == [], "明确选了不能看图的模型时，不偷偷换成豆包"


def test_no_ark_configured_keeps_old_behaviour(client, register, fake_llm):  # noqa: F811
    headers, _ = register()
    _provider(client, headers, "deepseek-chat", name="我的 DeepSeek")
    response = _recognize(client, headers, "课表.png", png_bytes())
    assert body(response, 422)["reason"] == "no_vision"


def test_settings_report_vision_model(client, auth, ark):
    data = body(client.get("/ai/settings", headers=auth))
    assert data["vision"] == {"configured": True, "name": "豆包（服务器配置）", "model": "doubao-seed-test"}
    assert "ark-test-key" not in json.dumps(data), "不把 Key 返回给前端"
