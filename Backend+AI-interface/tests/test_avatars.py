"""
自定义头像：上传后裁成 256px 正方形 JPEG；没配 COS 时存在本地目录；COS 配置齐全时走 COS 请求（这里用假连接，不访问外网）。
地址带内容版本号，换图后旧地址 404；删掉后改回 emoji。
"""

import io

import pytest
from conftest import body
from PIL import Image

from app.services import avatars


def _png(color=(216, 90, 48), size=(400, 300)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def local_store(tmp_path, monkeypatch):
    for key in ("COS_SECRET_ID", "COS_SECRET_KEY", "COS_REGION", "COS_BUCKET"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AVATAR_DIR", str(tmp_path))
    return tmp_path


def test_upload_replace_and_delete(client, register, local_store):
    headers, user = register()
    assert user["avatar_url"] == ""

    me = body(client.post("/users/me/avatar", headers=headers, files={"file": ("a.png", _png())}))
    url = me["avatar_url"]
    assert url.startswith(f"/users/avatar/{me['id']}/") and url.endswith(".jpg")
    assert me["avatar"] == "🦉", "emoji 头像保留，删掉图片后还能用"

    # 读取不需要登录；裁成 256 正方形
    image = client.get(url)
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert "immutable" in image.headers["cache-control"]
    assert Image.open(io.BytesIO(image.content)).size == (256, 256)
    assert len(list(local_store.rglob("*.jpg"))) == 1

    # 换一张：地址变了，旧地址 404，旧文件删掉
    second = body(client.post("/users/me/avatar", headers=headers, files={"file": ("b.png", _png((74, 123, 166)))}))
    assert second["avatar_url"] != url
    assert client.get(url).status_code == 404
    assert len(list(local_store.rglob("*.jpg"))) == 1

    gone = body(client.delete("/users/me/avatar", headers=headers))
    assert gone["avatar_url"] == "" and not list(local_store.rglob("*.jpg"))
    assert client.get(second["avatar_url"]).status_code == 404


def test_rejects_non_image_and_demo(client, register, local_store):
    headers, _ = register()
    bad = client.post("/users/me/avatar", headers=headers, files={"file": ("x.png", b"not an image")})
    assert bad.status_code == 415

    login = client.post("/auth/demo")
    if login.status_code == 200:
        demo = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
        assert client.post("/users/me/avatar", headers=demo, files={"file": ("a.png", _png())}).status_code == 403


def test_uses_cos_when_configured(client, register, monkeypatch):
    for key, value in {"COS_SECRET_ID": "id", "COS_SECRET_KEY": "key", "COS_REGION": "ap-guangzhou", "COS_BUCKET": "b-1"}.items():
        monkeypatch.setenv(key, value)
    store, calls = {}, []

    def fake(config, method, key, data=b"", connection=None):
        calls.append((method, key))
        if method == "PUT":
            store[key] = data
            return 200, b""
        if method == "GET":
            return (200, store[key]) if key in store else (404, b"")
        store.pop(key, None)
        return 204, b""

    monkeypatch.setattr(avatars, "_cos_request", fake)
    headers, _ = register()
    me = body(client.post("/users/me/avatar", headers=headers, files={"file": ("a.png", _png())}))
    assert calls[0][0] == "PUT" and calls[0][1].startswith(f"avatars/{me['id']}/")
    assert client.get(me["avatar_url"]).content == store[calls[0][1]]
    body(client.delete("/users/me/avatar", headers=headers))
    assert calls[-1][0] == "DELETE" and not store
