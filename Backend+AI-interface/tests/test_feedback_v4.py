"""v4 · 问题反馈：入库 + txt、截图校验、我的反馈、新反馈通知（机器人三种格式与钉钉加签、邮件）。"""

import base64
import hashlib
import hmac
import io
import json
import urllib.parse

import pytest
from PIL import Image

from conftest import body

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import AppSetting, Feedback
from app.services import mail, notify


def _png(size=(40, 30), mode="RGB", color=(80, 120, 200)) -> bytes:
    out = io.BytesIO()
    Image.new(mode, size, color).save(out, format="PNG")
    return out.getvalue()


def _jpeg_with_exif(size=(2400, 1200)) -> bytes:
    image = Image.new("RGB", size, (200, 100, 50))
    exif = Image.Exif()
    exif[0x010F] = "SecretCam"  # Make
    exif[0x0132] = "2026:01:01 08:00:00"  # DateTime
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif.tobytes())
    return out.getvalue()


def _upload(client, headers, content: bytes, name="shot.png", mime="image/png"):
    return client.post("/feedback/images", headers=headers, files={"file": (name, content, mime)})


@pytest.fixture
def clear_notify_settings():
    yield
    db = SessionLocal()
    try:
        db.query(AppSetting).filter(AppSetting.key.in_(notify.SETTING_KEYS)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


class _FakeResponse:
    def __init__(self, payload=b'{"errcode":0}'):
        self._payload = payload

    def read(self, *_):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture
def fake_webhook(monkeypatch):
    sent = []

    def _urlopen(request, timeout=None):
        sent.append({"url": request.full_url, "body": json.loads(request.data.decode("utf-8")), "timeout": timeout})
        return _FakeResponse()

    monkeypatch.setattr(notify.urllib.request, "urlopen", _urlopen)
    return sent


# ---------------------------------------------------------------- 入库 + txt
def test_feedback_saved_to_db_and_txt(client, register):
    headers, user = register("反馈同学")
    saved = body(client.post("/feedback", headers=headers, json={"category": "ui", "content": "按钮在深色模式下看不清", "page": "/settings", "contact": "qq 123"}))
    assert isinstance(saved["id"], int)
    db = SessionLocal()
    try:
        row = db.get(Feedback, saved["id"])
        assert row.user_id == user["id"] and row.status == "open" and row.category == "ui"
        assert row.txt_name == f"{saved['txt_id']}.txt"
    finally:
        db.close()
    text = (settings.FEEDBACK_DIR / f"{saved['txt_id']}.txt").read_text(encoding="utf-8")
    assert "界面问题" in text and "按钮在深色模式下看不清" in text and "qq 123" in text and "/settings" in text

    mine = body(client.get("/feedback/mine", headers=headers))
    assert mine["unread"] == 0 and mine["items"][0]["id"] == saved["id"] and mine["items"][0]["status_label"] == "待处理"
    # 别人的反馈看不到、也不能标记已读
    other, _ = register()
    assert body(client.get("/feedback/mine", headers=other))["items"] == []
    body(client.post(f"/feedback/{saved['id']}/read", headers=other), 404)


def test_feedback_daily_limit(client, register):
    headers, _ = register()
    for i in range(10):
        body(client.post("/feedback", headers=headers, json={"content": f"第 {i} 条反馈内容"}))
    body(client.post("/feedback", headers=headers, json={"content": "第 11 条反馈内容"}), 429)


# ---------------------------------------------------------------- 截图
def test_feedback_images_validated_and_reencoded(client, register):
    headers, user = register()
    uploaded = body(_upload(client, headers, _jpeg_with_exif(), "photo.jpg", "image/jpeg"))
    name = uploaded["name"]
    assert name.startswith(f"f{user['id']}_") and name.endswith(".jpg")
    stored = settings.FEEDBACK_DIR / "images" / name
    with Image.open(stored) as image:
        assert max(image.size) == 1600
        assert not image.getexif(), "EXIF 应已去除"
    assert b"SecretCam" not in stored.read_bytes()

    # 带透明通道的 PNG 保留为 PNG；webp 也接受
    assert body(_upload(client, headers, _png(mode="RGBA", color=(1, 2, 3, 100))))["name"].endswith(".png")
    webp = io.BytesIO()
    Image.new("RGB", (20, 20)).save(webp, format="WEBP")
    assert body(_upload(client, headers, webp.getvalue(), "a.webp", "image/webp"))["name"].endswith(".jpg")

    # 伪造类型：文本改名为 png、GIF、PNG 文件头 + 垃圾数据、超过 3MB
    body(_upload(client, headers, b"<script>alert(1)</script>", "evil.png", "image/png"), 400)
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    body(_upload(client, headers, gif.getvalue(), "a.png", "image/png"), 400)
    body(_upload(client, headers, b"\x89PNG\r\n\x1a\n" + b"\x00" * 200, "broken.png", "image/png"), 400)
    body(_upload(client, headers, b"\xff\xd8\xff" + b"\x00" * (3 * 1024 * 1024 + 10), "big.jpg", "image/jpeg"), 413)

    saved = body(client.post("/feedback", headers=headers, json={"content": "附上截图看看", "images": [name]}))
    assert saved["images"] == [name]
    assert "images/" + name in (settings.FEEDBACK_DIR / f"{saved['txt_id']}.txt").read_text(encoding="utf-8")
    assert body(client.get("/feedback/mine", headers=headers))["items"][0]["images"] == [name]

    # 本人能看图，别人不能；不能引用别人的截图、伪造的文件名，最多 3 张
    assert client.get(f"/feedback/images/{name}", headers=headers).headers["content-type"] == "image/jpeg"
    other, _ = register()
    body(client.get(f"/feedback/images/{name}", headers=other), 403)
    body(client.get("/feedback/images/..%2F..%2Fmain.py", headers=headers), 404)
    body(client.post("/feedback", headers=other, json={"content": "引用别人的截图", "images": [name]}), 400)
    body(client.post("/feedback", headers=headers, json={"content": "伪造的文件名", "images": ["../../main.py"]}), 400)
    body(client.post("/feedback", headers=headers, json={"content": "太多截图了啊", "images": [name] * 4}), 422)


# ---------------------------------------------------------------- 通知
def test_webhook_formats_and_dingtalk_sign(fake_webhook, monkeypatch):
    notify.post_webhook("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc", "", "标题", "正文")
    assert fake_webhook[-1]["body"] == {"msgtype": "text", "text": {"content": "标题\n正文"}}

    monkeypatch.setattr(notify.time, "time", lambda: 1700000000.123)
    notify.post_webhook("https://open.feishu.cn/open-apis/bot/v2/hook/xyz", "fs-secret", "标题", "正文")
    feishu = fake_webhook[-1]["body"]
    assert feishu["msg_type"] == "text" and feishu["content"]["text"] == "标题\n正文"
    expected = base64.b64encode(hmac.new(b"1700000000\nfs-secret", b"", hashlib.sha256).digest()).decode()
    assert feishu["timestamp"] == "1700000000" and feishu["sign"] == expected

    notify.post_webhook("https://oapi.dingtalk.com/robot/send?access_token=tk", "SECxyz", "标题", "正文")
    ding = fake_webhook[-1]
    assert ding["body"] == {"msgtype": "text", "text": {"content": "标题\n正文"}}
    query = urllib.parse.parse_qs(urllib.parse.urlparse(ding["url"]).query)
    assert query["access_token"] == ["tk"] and query["timestamp"] == ["1700000000123"]
    sign = base64.b64encode(hmac.new(b"SECxyz", b"1700000000123\nSECxyz", hashlib.sha256).digest()).decode()
    assert query["sign"] == [sign]

    assert notify.detect_kind("https://example.com/hook") == "generic"
    with pytest.raises(RuntimeError):
        notify.post_webhook("ftp://x", "", "a", "b")


def test_webhook_error_code_is_reported(monkeypatch):
    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda *a, **k: _FakeResponse(b'{"errcode":93000,"errmsg":"invalid key"}'))
    with pytest.raises(RuntimeError, match="invalid key"):
        notify.post_webhook("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=bad", "", "a", "b")


def test_new_feedback_notifies_webhook_and_email(client, register, fake_webhook, clear_notify_settings):
    # 默认（测试环境 FEEDBACK_WEBHOOK=""）不发送
    headers, user = register("通知同学")
    body(client.post("/feedback", headers=headers, json={"content": "没有配置时不应发送"}))
    assert fake_webhook == []

    db = SessionLocal()
    try:
        notify.set_setting(db, notify.KEY_WEBHOOK, "https://oapi.dingtalk.com/robot/send?access_token=tk")
        notify.set_setting(db, notify.KEY_SECRET, "SECabc")
        notify.set_setting(db, notify.KEY_EMAILS, "ops@example.com")
        notify.set_setting(db, notify.KEY_PUBLIC_URL, "https://app.example.com")
        db.commit()
    finally:
        db.close()
    saved = body(client.post("/feedback", headers=headers, json={"category": "bug", "content": "课表页面打不开了", "page": "/timetable"}))
    assert len(fake_webhook) == 1
    text = fake_webhook[0]["body"]["text"]["content"]
    assert f"新反馈 #{saved['id']}" in text and "功能异常" in text and "课表页面打不开了" in text
    assert "/timetable" in text and user["email"] in text and f"https://app.example.com/admin?tab=feedback&id={saved['id']}" in text
    assert "sign=" in fake_webhook[0]["url"]
    email = mail.last_to("ops@example.com")
    assert email and f"#{saved['id']}" in email["subject"] and "课表页面打不开了" in email["body"]


def test_notify_failure_does_not_break_submit(client, register, monkeypatch, clear_notify_settings):
    def _boom(*_a, **_k):
        raise OSError("network down")

    monkeypatch.setattr(notify.urllib.request, "urlopen", _boom)
    db = SessionLocal()
    try:
        notify.set_setting(db, notify.KEY_WEBHOOK, "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc")
        db.commit()
    finally:
        db.close()
    headers, _ = register()
    body(client.post("/feedback", headers=headers, json={"content": "通知失败也要提交成功"}))
