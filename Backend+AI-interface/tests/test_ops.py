"""
上线必需——登录锁定 / 限流存 SQLite（重启不丢）、错误激增告警（带冷却）、健康检查、
站点信息（备案号）、注册时记录同意的条款版本。
"""

import asyncio
import time

import pytest
from conftest import body

from app.core import ratelimit
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.models import AppSetting, RateEvent, User
from app.services import alerts


# ---------------------------------------------------------------- 限流存 SQLite
def test_login_lock_survives_restart_because_it_is_stored_in_sqlite(client, register):
    _, user = register()
    key = user["email"].lower()
    # 模拟"上一个进程"留下的失败记录：直接写库，不经过任何进程内状态
    now = time.time()
    with engine.begin() as conn:
        for i in range(settings.LOGIN_MAX_FAILS):
            conn.execute(RateEvent.__table__.insert().values(bucket=ratelimit.LOGIN_BUCKET, key=key, ts=now - i))
    locked = client.post("/auth/login", json={"identifier": user["email"], "password": "secret123"})
    assert locked.status_code == 429 and "分钟后再试" in locked.json()["message"]

    # 过期的失败记录不算
    ratelimit.reset(key)
    with engine.begin() as conn:
        for _ in range(settings.LOGIN_MAX_FAILS):
            conn.execute(RateEvent.__table__.insert().values(
                bucket=ratelimit.LOGIN_BUCKET, key=key, ts=now - settings.LOGIN_LOCK_MINUTES * 60 - 5))
    body(client.post("/auth/login", json={"identifier": user["email"], "password": "secret123"}))


def test_failures_are_written_to_the_database(client, register):
    _, user = register()
    body(client.post("/auth/login", json={"identifier": user["email"], "password": "wrong-pass"}), 401)
    db = SessionLocal()
    try:
        rows = db.query(RateEvent).filter(RateEvent.bucket == ratelimit.LOGIN_BUCKET,
                                          RateEvent.key == user["email"].lower()).count()
    finally:
        db.close()
    assert rows == 1
    # 登录成功清除该账号的失败记录
    body(client.post("/auth/login", json={"identifier": user["email"], "password": "secret123"}))
    assert ratelimit.count(ratelimit.LOGIN_BUCKET, user["email"].lower(), 3600) == 0


def test_generic_hit_window(client):
    assert all(ratelimit.hit("unit-test", "k", 3, 60) for _ in range(3))
    assert ratelimit.hit("unit-test", "k", 3, 60) is False
    assert ratelimit.hit("unit-test", "other", 3, 60) is True
    # 窗口外的记录不计入
    with engine.begin() as conn:
        conn.execute(RateEvent.__table__.delete().where(RateEvent.bucket == "unit-test"))
        for _ in range(3):
            conn.execute(RateEvent.__table__.insert().values(bucket="unit-test", key="k", ts=time.time() - 120))
    assert ratelimit.hit("unit-test", "k", 3, 60) is True


# ---------------------------------------------------------------- 告警
@pytest.fixture
def alert_sink(monkeypatch):
    """同步执行告警并记录发出的消息（不访问外网）。"""
    sent = []
    monkeypatch.setattr(alerts, "_spawn", lambda target, *args: target(*args))
    monkeypatch.setattr(alerts, "send", lambda title, text: sent.append((title, text)) or {"webhook": "ok", "email": None})
    db = SessionLocal()
    try:
        db.query(AppSetting).filter(AppSetting.key.like("alert_last_%")).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    for kind in alerts.KINDS.values():
        ratelimit.clear(kind["bucket"])
    return sent


def test_client_error_spike_alerts_once_with_cooldown(client, alert_sink, monkeypatch):
    monkeypatch.setattr(settings, "ALERT_CLIENT_ERRORS", 3)
    for i in range(2):
        body(client.post("/client-errors", json={"message": f"TypeError: spike {i}", "page": "/day"}))
    assert alert_sink == []
    body(client.post("/client-errors", json={"message": "TypeError: spike 2", "page": "/day"}))
    assert len(alert_sink) == 1
    title, text = alert_sink[0]
    assert "前端运行时错误" in title and "3 次" in text and "spike 2" in text
    # 冷却期内不再重复告警
    for i in range(3, 6):
        body(client.post("/client-errors", json={"message": f"TypeError: spike {i}"}))
    assert len(alert_sink) == 1
    # 冷却结束后再次达到阈值会告警
    db = SessionLocal()
    try:
        db.get(AppSetting, "alert_last_client").value = str(time.time() - settings.ALERT_COOLDOWN_MINUTES * 60 - 1)
        db.commit()
    finally:
        db.close()
    body(client.post("/client-errors", json={"message": "TypeError: again"}))
    assert len(alert_sink) == 2


def test_server_5xx_middleware_counts_and_alerts(alert_sink, monkeypatch):
    monkeypatch.setattr(settings, "ALERT_5XX", 2)

    async def failing(scope, receive, send):
        await send({"type": "http.response.start", "status": 503, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def crashing(scope, receive, send):
        raise RuntimeError("boom")

    async def fine(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def noop(message):
        return None

    scope = {"type": "http", "method": "GET", "path": "/task/list"}
    asyncio.run(alerts.ErrorAlertMiddleware(fine)(scope, None, noop))
    asyncio.run(alerts.ErrorAlertMiddleware(failing)(scope, None, noop))
    assert ratelimit.count(alerts.KINDS["5xx"]["bucket"], "", 60) == 1 and alert_sink == []
    with pytest.raises(RuntimeError):
        asyncio.run(alerts.ErrorAlertMiddleware(crashing)(scope, None, noop))
    assert len(alert_sink) == 1 and "5xx" in alert_sink[0][0] and "/task/list" in alert_sink[0][1]


def test_alert_threshold_zero_disables(alert_sink, monkeypatch):
    monkeypatch.setattr(settings, "ALERT_CLIENT_ERRORS", 0)
    for _ in range(5):
        alerts.record_client_error("x")
    assert alert_sink == []


def test_alerts_cli_usage():
    assert alerts.main([]) == 64


# ---------------------------------------------------------------- 健康检查、站点信息、条款同意
def test_health_checks_database(client):
    assert body(client.get("/health"))["status"] == "ok"


def test_site_info_is_public_and_hides_empty_beian(client, monkeypatch):
    monkeypatch.setattr(settings, "ICP_NUMBER", "")
    monkeypatch.setattr(settings, "POLICE_BEIAN", "")
    data = body(client.get("/site/info"))
    assert data["icp_number"] == "" and data["icp_url"] == "" and data["police_url"] == ""
    assert data["terms_version"] == settings.TERMS_VERSION and data["contact_email"]

    monkeypatch.setattr(settings, "ICP_NUMBER", "京ICP备00000000号-1")
    monkeypatch.setattr(settings, "POLICE_BEIAN", "京公网安备11010502000000号")
    data = body(client.get("/site/info"))
    assert data["icp_number"] == "京ICP备00000000号-1" and data["icp_url"] == "https://beian.miit.gov.cn/"
    assert data["police_url"].startswith("https://beian.mps.gov.cn/") and "11010502000000" in data["police_url"]


def test_register_records_agreed_terms_and_old_clients_still_work(client):
    import uuid

    email = f"t{uuid.uuid4().hex[:8]}@example.com"
    data = body(client.post("/auth/register", json={"email": email, "password": "secret123",
                                                    "agreed_terms_version": settings.TERMS_VERSION}))
    old_email = f"o{uuid.uuid4().hex[:8]}@example.com"
    old = body(client.post("/auth/register", json={"email": old_email, "password": "secret123"}))
    db = SessionLocal()
    try:
        agreed = db.get(User, data["user"]["id"])
        legacy = db.get(User, old["user"]["id"])
        assert agreed.terms_version == settings.TERMS_VERSION and agreed.terms_agreed_at is not None
        assert legacy.terms_version is None and legacy.terms_agreed_at is None
    finally:
        db.close()
