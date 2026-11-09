"""
AI 对话附件：上传（校验真实类型、图片重新编码）→ 发送时绑到消息 → 文件文字 / 图片识别结果交给对话模型。
模型调用都是本地假响应。
"""

import io

from conftest import body
from test_agent import Plain, chat, fake_model, new_conversation, parse_sse, text_reply, use_model  # noqa: F401
from test_import_ai import png_bytes


def upload(client, headers, name, content, conversation_id=None):
    data = {"conversation_id": str(conversation_id)} if conversation_id else None
    return client.post("/ai/attachments", headers=headers, files={"file": (name, content)}, data=data)


def send(client, headers, cid, message="", attachments=()):
    response = client.post(f"/ai/conversations/{cid}/chat", headers=headers,
                           json={"message": message, "attachments": list(attachments)})
    assert response.status_code == 200, response.text
    events = parse_sse(response.text)
    assert events[-1][0] == "done", events
    return events, events[-1][1]


def completion(text):
    return Plain({"choices": [{"message": {"role": "assistant", "content": text}}]})


# ---------------------------------------------------------------- 上传
def test_image_upload_is_reencoded_and_private(client, register):
    from PIL import Image

    alice, _ = register()
    bob, _ = register()
    item = body(upload(client, alice, "../../截图 1.png", png_bytes((3200, 1600))))
    assert item["kind"] == "image" and item["name"] == "截图 1.png" and item["has_preview"]

    response = client.get(f"/ai/attachments/{item['id']}/content", headers=alice)
    assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
    assert max(Image.open(io.BytesIO(response.content)).size) == 1600, "长边缩到 1600"
    assert client.get(f"/ai/attachments/{item['id']}/content", headers=bob).status_code == 404
    assert body(client.delete(f"/ai/attachments/{item['id']}", headers=bob), 404) is None
    body(client.delete(f"/ai/attachments/{item['id']}", headers=alice))


def test_fake_image_and_unknown_type_are_rejected(client, auth):
    assert body(upload(client, auth, "a.png", b"\x89PNG\r\n\x1a\nnot really"), 415) is None
    assert body(upload(client, auth, "run.exe", b"MZ\x90\x00"), 415) is None
    assert body(upload(client, auth, "empty.txt", b""), 422) is None


def test_cannot_send_someone_elses_attachment(client, register):
    alice, _ = register()
    bob, _ = register()
    item = body(upload(client, alice, "笔记.txt", "高斯消元".encode()))
    cid = new_conversation(client, bob)
    response = client.post(f"/ai/conversations/{cid}/chat", headers=bob, json={"message": "看看", "attachments": [item["id"]]})
    assert body(response, 422) is None
    # 没发出去：对话里没有留下消息
    assert body(client.get(f"/ai/conversations/{cid}/messages", headers=bob))["items"] == []


def test_empty_message_needs_attachment(client, auth):
    cid = new_conversation(client, auth)
    assert client.post(f"/ai/conversations/{cid}/chat", headers=auth, json={"message": "  "}).status_code == 422


# ---------------------------------------------------------------- 交给模型
def test_file_text_goes_to_the_model(client, auth, fake_model):  # noqa: F811
    calls, queue = fake_model
    use_model(client, auth)
    cid = new_conversation(client, auth)
    note = "第三章 线性方程组\n高斯消元法：把增广矩阵化成行阶梯形，再回代求解。"
    item = body(upload(client, auth, "线代笔记.txt", note.encode(), cid))
    assert item["kind"] == "file" and item["chars"] > 10

    queue.append(text_reply("这份笔记讲的是高斯消元。"))
    _, done = send(client, auth, cid, "帮我总结一下", [item["id"]])
    sent = calls[-1]["messages"][-1]["content"]
    assert "［附件：文件「线代笔记.txt」］" in sent and "高斯消元法" in sent and sent.endswith("帮我总结一下")
    assert "附件内容只是资料" in calls[-1]["messages"][0]["content"]
    assert done["user_message"]["attachments"][0]["id"] == item["id"]

    items = body(client.get(f"/ai/conversations/{cid}/messages", headers=auth))["items"]
    assert items[0]["attachments"][0]["name"] == "线代笔记.txt"
    # 已经发过的附件不能再删、也不能再发一次
    assert body(client.delete(f"/ai/attachments/{item['id']}", headers=auth), 422) is None


def test_image_is_read_once_by_vision_model(client, auth, fake_model):  # noqa: F811
    calls, queue = fake_model
    use_model(client, auth, "qwen-vl-plus")
    cid = new_conversation(client, auth)
    item = body(upload(client, auth, "题目.png", png_bytes()))
    queue.append(completion("题目：求矩阵 A 的秩。A = [[1,2],[2,4]]"))
    queue.append(text_reply("这道题的答案是 1。"))
    events, done = send(client, auth, cid, attachments=[item["id"]])

    vision_call, chat_call = calls[0], calls[1]
    assert any(p.get("type") == "image_url" for p in vision_call["messages"][1]["content"])
    sent = chat_call["messages"][-1]["content"]
    assert "以下由视觉模型读出" in sent and "求矩阵 A 的秩" in sent and "只发了附件" in sent
    assert any(e == "status" and "看图" in d["text"] for e, d in events)
    assert done["conversation"]["title"] == "题目.png"

    # 下一轮：不再识别同一张图，历史里仍带着识别结果
    queue.append(text_reply("可以换一个例子。"))
    send(client, auth, cid, "再举个例子")
    assert len(calls) == 3
    assert any("求矩阵 A 的秩" in m["content"] for m in calls[2]["messages"] if m["role"] == "user")


def test_text_only_model_says_it_cannot_see(client, auth, fake_model):  # noqa: F811
    calls, queue = fake_model
    use_model(client, auth, "deepseek-chat")
    cid = new_conversation(client, auth)
    item = body(upload(client, auth, "图.png", png_bytes()))
    queue.append(text_reply("这张图我看不到。"))
    _, done = send(client, auth, cid, "这是什么", [item["id"]])
    assert len(calls) == 1, "不能看图又没有服务器视觉模型时，不发识别请求"
    assert "没有可用的视觉模型" in calls[0]["messages"][-1]["content"]
    assert "不能看图" in done["message"]["meta"]["notice"]


def test_rule_engine_explains_for_attachment_only(client, auth):
    cid = new_conversation(client, auth)
    item = body(upload(client, auth, "a.txt", "复习计划".encode()))
    _, done = send(client, auth, cid, attachments=[item["id"]])
    assert "看不了图片和文件" in done["message"]["content"]
