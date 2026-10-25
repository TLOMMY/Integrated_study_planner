"""v4 · 管理后台：权限、反馈处理与回复、用户管理、看板、前端错误上报、通知设置。"""

import json

import pytest

from conftest import body

from app.core.database import SessionLocal
from app.models import AppSetting, ClientError, User
from app.services import mail, notify

ADMIN = "admin@example.com"


@pytest.fixture
def admin(client):
    response = client.post("/auth/register", json={"email": ADMIN, "password": "secret123", "full_name": "管理员"})
    if response.status_code == 200:
        data = response.json()["data"]
    else:
        data = body(client.post("/auth/login", json={"identifier": ADMIN, "password": "secret123"}))
    assert data["user"]["is_admin"] is True
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


@pytest.fixture(autouse=True)
def _clear_settings():
    yield
    db = SessionLocal()
    try:
        db.query(AppSetting).filter(AppSetting.key.in_(notify.SETTING_KEYS)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


ADMIN_GETS = ["/admin/feedback", "/admin/users", "/admin/dashboard", "/admin/errors", "/admin/settings"]


def test_normal_user_gets_403(client, auth):
    for path in ADMIN_GETS:
        body(client.get(path, headers=auth), 403)
    body(client.get("/admin/feedback/1", headers=auth), 403)
    body(client.put("/admin/users/1", headers=auth, json={"is_active": False}), 403)
    body(client.post("/admin/users/1/reset-password", headers=auth), 403)
    body(client.put("/admin/settings", headers=auth, json={"feedback_webhook": ""}), 403)
    body(client.post("/admin/settings/test-notify", headers=auth), 403)
    body(client.post("/admin/feedback/1/reply", headers=auth, json={"reply": "hi"}), 403)
    body(client.get("/admin/dashboard"), 401)


def test_feedback_workflow_reply_and_unread(client, register, admin):
    admin_headers, _ = admin
    headers, user = register("提问同学")
    saved = body(client.post("/feedback", headers=headers, json={"category": "suggestion", "content": "希望增加深色模式开关", "page": "/settings"}))

    listing = body(client.get("/admin/feedback", headers=admin_headers, params={"status": "open", "q": "深色模式"}))
    assert listing["items"][0]["id"] == saved["id"] and listing["items"][0]["user"]["email"] == user["email"]
    assert listing["counts"]["open"] >= 1
    assert body(client.get("/admin/feedback", headers=admin_headers, params={"q": user["email"]}))["total"] >= 1
    assert body(client.get("/admin/feedback", headers=admin_headers, params={"category": "bug", "q": "深色模式"}))["total"] == 0

    detail = body(client.get(f"/admin/feedback/{saved['id']}", headers=admin_headers))
    assert detail["user"]["id"] == user["id"] and detail["client"] and detail["txt_name"]
    body(client.put(f"/admin/feedback/{saved['id']}/status", headers=admin_headers, json={"status": "bogus"}), 422)

    replied = body(client.post(f"/admin/feedback/{saved['id']}/reply", headers=admin_headers,
                               json={"reply": "已经在做了，下个版本上线", "send_email": True}))
    assert replied["status"] == "processing" and replied["emailed"] is True and replied["replied_by_name"] == "管理员"
    email = mail.last_to(user["email"])
    assert email and "已经在做了" in email["body"]

    mine = body(client.get("/feedback/mine", headers=headers))
    assert mine["unread"] == 1
    item = mine["items"][0]
    assert item["reply"] == "已经在做了，下个版本上线" and item["unread"] is True and item["status"] == "processing"
    assert "contact" not in item and "user" not in item, "用户接口不暴露后台字段"
    body(client.post(f"/feedback/{saved['id']}/read", headers=headers))
    assert body(client.get("/feedback/mine", headers=headers))["unread"] == 0

    done = body(client.put(f"/admin/feedback/{saved['id']}/status", headers=admin_headers, json={"status": "resolved"}))
    assert done["status"] == "resolved"
    assert body(client.get("/feedback/mine", headers=headers))["items"][0]["status_label"] == "已解决"


def test_admin_can_view_feedback_image(client, register, admin):
    import io

    from PIL import Image

    admin_headers, _ = admin
    headers, _ = register()
    raw = io.BytesIO()
    Image.new("RGB", (30, 30), (10, 20, 30)).save(raw, format="PNG")
    name = body(client.post("/feedback/images", headers=headers, files={"file": ("a.png", raw.getvalue(), "image/png")}))["name"]
    saved = body(client.post("/feedback", headers=headers, json={"content": "带截图的反馈", "images": [name]}))
    assert body(client.get(f"/admin/feedback/{saved['id']}", headers=admin_headers))["images"] == [name]
    assert client.get(f"/feedback/images/{name}", headers=admin_headers).status_code == 200


def test_user_management_disable_reset_and_admin(client, register, admin):
    admin_headers, me = admin
    headers, user = register("被管理的同学")
    body(client.post("/task/create", headers=headers, json={"title": "看书", "duration_minutes": 30}))

    found = body(client.get("/admin/users", headers=admin_headers, params={"q": user["email"]}))
    assert found["total"] == 1 and found["items"][0]["task_count"] == 1 and found["items"][0]["last_seen_at"]
    detail = body(client.get(f"/admin/users/{user['id']}", headers=admin_headers))
    assert detail["created_at"] and detail["active_days_30"] == 1 and detail["focus_minutes"] == 0

    # 停用：已有登录立即失效、无法再登录；启用后恢复
    body(client.put(f"/admin/users/{user['id']}", headers=admin_headers, json={"is_active": False}))
    body(client.get("/users/me", headers=headers), 403)
    body(client.post("/auth/login", json={"identifier": user["email"], "password": "secret123"}), 403)
    assert body(client.get("/admin/users", headers=admin_headers, params={"status": "disabled", "q": user["email"]}))["total"] == 1
    body(client.put(f"/admin/users/{user['id']}", headers=admin_headers, json={"is_active": True}))
    body(client.get("/users/me", headers=headers))

    # 重置密码：临时密码只返回一次，旧凭证与旧密码失效
    temp = body(client.post(f"/admin/users/{user['id']}/reset-password", headers=admin_headers))["temp_password"]
    assert len(temp) == 10
    body(client.get("/users/me", headers=headers), 401)
    body(client.post("/auth/login", json={"identifier": user["email"], "password": "secret123"}), 401)
    body(client.post("/auth/login", json={"identifier": user["email"], "password": temp}))

    # 设为管理员后可访问后台；不能取消自己、不能停用自己、不能重置自己
    promoted = body(client.put(f"/admin/users/{user['id']}", headers=admin_headers, json={"is_admin": True}))
    assert promoted["is_admin"] is True
    login = body(client.post("/auth/login", json={"identifier": user["email"], "password": temp}))
    assert login["user"]["is_admin"] is True
    body(client.get("/admin/dashboard", headers={"Authorization": f"Bearer {login['access_token']}"}))
    body(client.put(f"/admin/users/{user['id']}", headers=admin_headers, json={"is_admin": False}))
    body(client.get("/admin/dashboard", headers={"Authorization": f"Bearer {login['access_token']}"}), 403)

    body(client.put(f"/admin/users/{me['id']}", headers=admin_headers, json={"is_admin": False}), 400)
    body(client.put(f"/admin/users/{me['id']}", headers=admin_headers, json={"is_active": False}), 400)
    body(client.post(f"/admin/users/{me['id']}/reset-password", headers=admin_headers), 400)
    body(client.get("/admin/users/999999", headers=admin_headers), 404)


def test_dashboard(client, register, admin):
    admin_headers, _ = admin
    register()
    data = body(client.get("/admin/dashboard", headers=admin_headers))
    assert data["users"]["total"] >= 2 and data["users"]["new_today"] >= 1 and data["users"]["dau"] >= 1
    assert len(data["trend"]) == 14 and data["trend"][-1]["new_users"] >= 1
    assert set(data["feedback"]["by_status"]) == {"open", "processing", "resolved", "closed"}
    assert {"messages_total", "conversations"} <= set(data["ai"]) and "occurrences_7d" in data["errors"]


def test_client_errors_aggregated(client, auth, admin):
    admin_headers, _ = admin
    report = {"message": "TypeError: x is undefined", "stack": "TypeError: x is undefined\n    at load (http://h/assets/Home-abc.js?v=1:1:200)\n    at run (x.js:2:3)",
              "page": "/today-task", "version": "4.0.0", "info": "setup function"}
    first = body(client.post("/client-errors", json=report))
    second = body(client.post("/client-errors", headers=auth, json={**report, "page": "/day",
                                                                     "stack": report["stack"].replace("?v=1", "?v=2")}))
    assert first["fingerprint"] == second["fingerprint"] and second["count"] == 2
    other = body(client.post("/client-errors", json={**report, "message": "ReferenceError: y"}))
    assert other["fingerprint"] != first["fingerprint"]
    body(client.post("/client-errors", json={"message": ""}), 422)

    listing = body(client.get("/admin/errors", headers=admin_headers, params={"q": "x is undefined"}))
    row = listing["items"][0]
    assert row["count"] == 2 and row["page"] == "/day" and row["version"] == "4.0.0" and "at load" in row["stack"]
    assert body(client.get("/admin/dashboard", headers=admin_headers))["errors"]["occurrences_7d"] >= 3
    body(client.delete(f"/admin/errors/{row['id']}", headers=admin_headers))
    assert body(client.get("/admin/errors", headers=admin_headers, params={"q": "x is undefined"}))["total"] == 0


def test_client_errors_rate_limited(client):
    statuses = [client.post("/client-errors", json={"message": f"spam {i}"}).status_code for i in range(35)]
    assert statuses.count(200) == 30 and statuses[-1] == 429
    db = SessionLocal()
    try:
        db.query(ClientError).filter(ClientError.message.like("spam %")).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_settings_masked_and_test_notify(client, admin, monkeypatch):
    admin_headers, _ = admin
    sent = []

    class _Resp:
        def read(self, *_):
            return b'{"errcode":0}'

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda req, timeout=None: sent.append(json.loads(req.data)) or _Resp())

    initial = body(client.get("/admin/settings", headers=admin_headers))
    assert initial["feedback_webhook_set"] is False and initial["mail_backend"] == "memory"
    body(client.post("/admin/settings/test-notify", headers=admin_headers), 400)
    body(client.put("/admin/settings", headers=admin_headers, json={"feedback_webhook": "javascript:alert(1)"}), 422)
    body(client.put("/admin/settings", headers=admin_headers, json={"feedback_notify_emails": "not-an-email"}), 422)

    url = "https://open.feishu.cn/open-apis/bot/v2/hook/0123456789abcdef"
    saved = body(client.put("/admin/settings", headers=admin_headers, json={
        "feedback_webhook": url, "feedback_webhook_secret": "very-secret-value", "feedback_notify_emails": "a@example.com；b@example.com"}))
    assert saved["feedback_webhook_kind"] == "飞书" and saved["source"]["feedback_webhook"] == "admin"
    assert url not in json.dumps(saved) and "very-secret-value" not in json.dumps(saved)
    assert saved["feedback_webhook_masked"].endswith("cdef") and saved["feedback_webhook_secret_set"] is True
    assert saved["feedback_notify_emails"] == "a@example.com,b@example.com"

    # 只改邮箱时机器人地址保持不变
    body(client.put("/admin/settings", headers=admin_headers, json={"feedback_notify_emails": "ops@example.com"}))
    result = body(client.post("/admin/settings/test-notify", headers=admin_headers))
    assert result == {"webhook": "ok", "email": "ok"}
    assert sent[-1]["msg_type"] == "text" and "sign" in sent[-1] and "测试通知" in sent[-1]["content"]["text"]
    assert mail.last_to("ops@example.com")["subject"] == "【学业管家】测试通知"

    # 清空后不再发送
    cleared = body(client.put("/admin/settings", headers=admin_headers, json={"feedback_webhook": "", "feedback_notify_emails": ""}))
    assert cleared["feedback_webhook_set"] is False


def test_demo_account_disabled_blocks_demo_login(client, admin):
    admin_headers, _ = admin
    demo = body(client.post("/auth/demo"))["user"]
    body(client.put(f"/admin/users/{demo['id']}", headers=admin_headers, json={"is_active": False}))
    try:
        body(client.post("/auth/demo"), 403)
    finally:
        body(client.put(f"/admin/users/{demo['id']}", headers=admin_headers, json={"is_active": True}))
    db = SessionLocal()
    try:
        assert db.get(User, demo["id"]).is_active is True
    finally:
        db.close()
