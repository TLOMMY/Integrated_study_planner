"""
前后端契约测试：扫描前端 src/api/index.js 里的每一个请求，
确认"方法 + 路径"都能在后端 OpenAPI 中找到，杜绝接口路径/方法不匹配。
"""

import re
from pathlib import Path

import pytest

FRONTEND_API = Path(__file__).resolve().parents[2] / "Frontend" / "src" / "api" / "index.js"
CALL = re.compile(r"http\.(get|post|put|delete)\(\s*(?:'([^']+)'|`([^`]+)`)")


def _frontend_calls():
    source = FRONTEND_API.read_text(encoding="utf-8")
    calls = set()
    for method, plain, template in CALL.findall(source):
        path = plain or re.sub(r"\$\{[^}]+\}", "{}", template)
        calls.add((method.upper(), path))
    return calls


def _backend_routes(client):
    spec = client.get("/openapi.json").json()
    return {
        (method.upper(), re.sub(r"\{[^}]+\}", "{}", path))
        for path, operations in spec["paths"].items()
        for method in operations
    }


@pytest.mark.skipif(not FRONTEND_API.exists(), reason="前端代码不在同一仓库")
def test_every_frontend_call_exists_in_backend(client):
    calls = _frontend_calls()
    assert len(calls) >= 25, "前端接口扫描结果异常"
    missing = sorted(calls - _backend_routes(client))
    assert not missing, f"前端调用了后端不存在的接口：{missing}"


ADMIN_ONLY = {"/feedback"}


def test_all_business_routes_return_envelope(client, auth):
    """所有 GET 业务接口都返回 {code, message, data}。"""
    for method, path in sorted(_backend_routes(client)):
        if method != "GET" or "{}" in path or path in {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}:
            continue
        payload = client.get(path, headers=auth).json()
        assert set(payload) == {"code", "message", "data"}, path
        # 管理员接口对普通账号返回 403，同样是标准信封
        expected = 403 if path in ADMIN_ONLY else 200
        assert payload["code"] == expected, (path, payload)
