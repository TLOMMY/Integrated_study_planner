from conftest import body


def test_register_returns_token_and_profile(client, register):
    headers, user = register("小王")
    assert user["display_name"] == "小王" and user["daily_goal_minutes"] == 60
    me = body(client.get("/users/me", headers=headers))
    assert me["id"] == user["id"]


def test_login_by_email_and_wrong_password(client, register):
    _, user = register()
    data = body(client.post("/auth/login", json={"identifier": user["email"], "password": "secret123"}))
    assert data["token_type"] == "bearer" and data["expires_in"] > 0
    error = client.post("/auth/login", json={"email": user["email"], "password": "wrong"})
    assert body(error, 401) is None
    assert error.json()["message"] == "账号或密码错误"


def test_duplicate_email_rejected(client, register):
    _, user = register()
    response = client.post("/auth/register", json={"email": user["email"], "password": "secret123"})
    body(response, 400)
    assert "已注册" in response.json()["message"]


def test_validation_errors_are_chinese(client):
    response = client.post("/auth/register", json={"email": "bad", "password": "1"})
    body(response, 422)
    assert response.json()["message"] in {"邮箱格式不正确", "密码至少需要 6 个字符"}
    assert response.json()["data"]["errors"]


def test_protected_routes_require_token(client):
    for path in ["/users/me", "/task/list", "/timetable", "/study/stats", "/home/summary", "/study-plans"]:
        assert body(client.get(path), 401) is None
    assert body(client.get("/task/list", headers={"Authorization": "Bearer nonsense"}), 401) is None


def test_update_profile_and_password(client, register):
    headers, user = register()
    data = body(client.put("/users/me", headers=headers, json={"full_name": "新名字", "avatar": "🐼", "daily_goal_minutes": 90}))
    assert data["display_name"] == "新名字" and data["avatar"] == "🐼" and data["daily_goal_minutes"] == 90
    body(client.put("/users/me/password", headers=headers, json={"old_password": "nope", "new_password": "abcdef"}), 400)
    body(client.put("/users/me/password", headers=headers, json={"old_password": "secret123", "new_password": "abcdef"}))
    body(client.post("/auth/login", json={"identifier": user["email"], "password": "abcdef"}))


def test_refresh_and_demo_login(client):
    data = body(client.post("/auth/demo"))
    assert data["user"]["is_demo"] is True
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    assert body(client.post("/auth/refresh", headers=headers))["access_token"]
    # 演示账号密码可用，且不允许修改
    body(client.post("/auth/login", json={"identifier": "demo@example.com", "password": "demo123456"}))
    body(client.put("/users/me/password", headers=headers, json={"old_password": "demo123456", "new_password": "x12345"}), 403)


def test_unknown_route_envelope(client):
    assert body(client.get("/no-such-route"), 404) is None
