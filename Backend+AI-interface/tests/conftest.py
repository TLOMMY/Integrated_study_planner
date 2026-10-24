"""
测试夹具：每次测试会话使用独立的临时 SQLite，且强制关闭 DeepSeek，避免真实网络调用。
环境变量必须在 import main 之前设置。
"""

import os
import tempfile
import uuid
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="study_planner_test_"))
os.environ["DATABASE_URL"] = "sqlite:///" + (_TMP / "test.db").as_posix()
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["SEED_DEMO"] = "1"
os.environ["FEEDBACK_DIR"] = (_TMP / "feedback").as_posix()
os.environ["ADMIN_EMAILS"] = "admin@example.com"

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_login_limit():
    from app.core import ratelimit

    ratelimit.reset()
    yield


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def register(client):
    def _make(name: str = "测试同学"):
        email = f"u{uuid.uuid4().hex[:10]}@example.com"
        response = client.post("/auth/register", json={"email": email, "password": "secret123", "full_name": name})
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]

    return _make


@pytest.fixture
def auth(register):
    headers, _ = register()
    return headers


def body(response, status: int = 200):
    """断言 HTTP 状态与信封 code 一致，返回 data。"""
    payload = response.json()
    assert response.status_code == status, payload
    assert payload["code"] == status and isinstance(payload["message"], str)
    return payload["data"]
