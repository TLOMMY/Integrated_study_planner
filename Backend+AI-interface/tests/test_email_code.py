"""v4 · 邮箱验证码：注册验证、找回密码、验证 / 换绑邮箱；过期、错误次数、发送频率。"""

import re
import uuid
from datetime import timedelta

import pytest

from conftest import body

from app.core import timeutil
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import EmailCode
from app.services import mail


def _email() -> str:
    return f"c{uuid.uuid4().hex[:10]}@example.com"


def _code_for(address: str) -> str:
    message = mail.last_to(address)
    assert message, f"没有发给 {address} 的邮件"
    return re.search(r"验证码是：(\d{6})", message["body"]).group(1)


def _age_codes(address: str, seconds: int = 120) -> None:
    """把该邮箱的验证码发送时间往前挪，绕过 60 秒冷却。"""
    db = SessionLocal()
    try:
        for row in db.query(EmailCode).filter(EmailCode.email == address):
            row.created_at = row.created_at - timedelta(seconds=seconds)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def require_verify(monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFY", True)


def test_options_and_register_with_code(client):
    assert body(client.get("/auth/options")) == {"require_email_verify": False, "mail_enabled": True}
    address = _email()
    sent = body(client.post("/auth/email-code", json={"email": address, "purpose": "register"}))
    assert sent["cooldown"] == 60 and sent["expires_in"] == 600
    code = _code_for(address)
    db = SessionLocal()
    try:
        row = db.query(EmailCode).filter(EmailCode.email == address).one()
        assert code not in row.code_hash, "只能存哈希"
    finally:
        db.close()
    user = body(client.post("/auth/register", json={"email": address, "password": "secret123", "code": code}))["user"]
    assert user["email_verified"] is True
    # 已注册的邮箱不能再发注册验证码
    _age_codes(address)
    body(client.post("/auth/email-code", json={"email": address, "purpose": "register"}), 400)


def test_register_without_code_still_works_by_default(client):
    user = body(client.post("/auth/register", json={"email": _email(), "password": "secret123"}))["user"]
    assert user["email_verified"] is False


def test_register_requires_code_when_enabled(client, require_verify):
    address = _email()
    body(client.post("/auth/register", json={"email": address, "password": "secret123"}), 400)
    body(client.post("/auth/register", json={"email": address, "password": "secret123", "code": "000000"}), 400)
    body(client.post("/auth/email-code", json={"email": address, "purpose": "register"}))
    body(client.post("/auth/register", json={"email": address, "password": "secret123", "code": _code_for(address)}))


def test_code_cooldown_daily_limit_attempts_and_expiry(client, monkeypatch):
    address = _email()
    body(client.post("/auth/email-code", json={"email": address, "purpose": "register"}))
    limited = body(client.post("/auth/email-code", json={"email": address, "purpose": "register"}), 429)
    assert 0 < limited["retry_after"] <= 60

    # 错误 5 次后作废，正确的也不能再用
    code = _code_for(address)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(4):
        body(client.post("/auth/register", json={"email": address, "password": "secret123", "code": wrong}), 400)
    last = client.post("/auth/register", json={"email": address, "password": "secret123", "code": wrong}).json()
    assert "过多" in last["message"]
    body(client.post("/auth/register", json={"email": address, "password": "secret123", "code": code}), 400)

    # 过期
    _age_codes(address)
    body(client.post("/auth/email-code", json={"email": address, "purpose": "register"}))
    code = _code_for(address)
    real_now = timeutil.now
    monkeypatch.setattr(timeutil, "now", lambda: real_now() + timedelta(minutes=11))
    expired = client.post("/auth/register", json={"email": address, "password": "secret123", "code": code}).json()
    assert expired["code"] == 400 and "过期" in expired["message"]
    monkeypatch.setattr(timeutil, "now", real_now)

    # 重新发送后旧码作废，只有最新的有效
    _age_codes(address)
    body(client.post("/auth/email-code", json={"email": address, "purpose": "register"}))
    first = _code_for(address)
    _age_codes(address)
    body(client.post("/auth/email-code", json={"email": address, "purpose": "register"}))
    second = _code_for(address)
    if first != second:
        body(client.post("/auth/register", json={"email": address, "password": "secret123", "code": first}), 400)
    body(client.post("/auth/register", json={"email": address, "password": "secret123", "code": second}))

    # 每日上限
    monkeypatch.setattr(settings, "EMAIL_CODE_DAILY_LIMIT", 2)
    other = _email()
    body(client.post("/auth/email-code", json={"email": other, "purpose": "register"}))
    _age_codes(other)
    body(client.post("/auth/email-code", json={"email": other, "purpose": "register"}))
    _age_codes(other)
    assert "明天" in client.post("/auth/email-code", json={"email": other, "purpose": "register"}).json()["message"]


def test_reset_password_flow(client, register):
    headers, user = register()
    address = user["email"]
    # 未注册的邮箱：同样提示已发送，但不真的发
    ghost = _email()
    body(client.post("/auth/email-code", json={"email": ghost, "purpose": "reset"}))
    assert mail.last_to(ghost) is None
    body(client.post("/auth/reset-password", json={"email": ghost, "code": "123456", "new_password": "newpass1"}), 400)

    body(client.post("/auth/email-code", json={"email": address, "purpose": "reset"}))
    code = _code_for(address)
    body(client.post("/auth/reset-password", json={"email": address, "code": code, "new_password": "brandnew1"}))
    # 旧登录失效、旧密码不能用、新密码可以；验证码不能复用
    body(client.get("/users/me", headers=headers), 401)
    body(client.post("/auth/login", json={"identifier": address, "password": "secret123"}), 401)
    me = body(client.post("/auth/login", json={"identifier": address, "password": "brandnew1"}))["user"]
    assert me["email_verified"] is True
    body(client.post("/auth/reset-password", json={"email": address, "code": code, "new_password": "again123"}), 400)


def test_verify_and_change_email(client, register, monkeypatch):
    headers, user = register()
    _, other = register()
    body(client.post("/auth/email-code", json={"email": user["email"], "purpose": "bind"}), 401)
    body(client.post("/auth/email-code", headers=headers, json={"email": user["email"], "purpose": "bind"}))
    body(client.post("/users/me/verify-email", headers=headers, json={"code": "12345"}), 422)
    verified = body(client.post("/users/me/verify-email", headers=headers, json={"code": _code_for(user["email"])}))
    assert verified["email_verified"] is True

    # 未开启强制验证：不带验证码也能换绑，但新邮箱变为未验证
    new_email = _email()
    changed = body(client.put("/users/me/email", headers=headers, json={"email": new_email, "password": "secret123"}))
    assert changed["email"] == new_email and changed["email_verified"] is False

    # 开启后必须带新邮箱的验证码
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFY", True)
    newer = _email()
    body(client.put("/users/me/email", headers=headers, json={"email": newer, "password": "secret123"}), 400)
    body(client.post("/auth/email-code", headers=headers, json={"email": newer, "purpose": "bind"}))
    changed = body(client.put("/users/me/email", headers=headers, json={"email": newer, "password": "secret123", "code": _code_for(newer)}))
    assert changed["email"] == newer and changed["email_verified"] is True

    # 不能给别人的邮箱发绑定码
    body(client.post("/auth/email-code", headers=headers, json={"email": other["email"], "purpose": "bind"}), 400)
