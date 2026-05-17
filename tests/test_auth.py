import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_register_and_login():
    # 注册
    reg_resp = client.post("/api/auth/register", json={
        "username": "testuser",
        "password": "testpass123"
    })
    assert reg_resp.status_code == 201
    data = reg_resp.json()
    assert "id" in data
    assert data["username"] == "testuser"

    # 登录
    login_resp = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "testpass123"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # 访问受保护接口
    me_resp = client.get("/api/user/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "testuser"

def test_register_duplicate():
    # 先注册一次
    client.post("/api/auth/register", json={"username": "duplicate", "password": "pwd"})
    # 再次注册相同用户名
    resp = client.post("/api/auth/register", json={"username": "duplicate", "password": "pwd"})
    assert resp.status_code == 400
    assert "already registered" in resp.text