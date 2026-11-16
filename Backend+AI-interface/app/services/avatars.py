# -*- coding: utf-8 -*-
"""
自定义头像：上传的图片裁成正方形、缩到 256px、重编码为 JPEG（去掉 EXIF 等元数据），
配了腾讯云 COS（COS_SECRET_ID / COS_SECRET_KEY / COS_REGION / COS_BUCKET）就存到桶里的 COS_AVATAR_PREFIX 目录，
没配就存在本地 AVATAR_DIR。对外一律经后端 GET /users/avatar/{user_id}/{version}.jpg 读取，桶保持私有、不暴露密钥。

User.avatar 仍然只存 emoji（String(16)）；自定义头像另存在 avatar_image（对象键），非空时优先显示图片。
"""

import hashlib
import io
import os
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.errors import ApiError
from app.models import User

SIZE = 256
QUALITY = 86
MAX_PIXELS = 40_000_000
CACHE_SECONDS = 30 * 24 * 3600


def cos_config() -> Optional[dict]:
    """服务器配了 COS 时返回配置（与异地备份共用同一组变量），否则 None。"""
    values = {key: os.environ.get(key, "").strip() for key in ("COS_SECRET_ID", "COS_SECRET_KEY", "COS_REGION", "COS_BUCKET")}
    return values if all(values.values()) else None


def _prefix() -> str:
    return (os.environ.get("COS_AVATAR_PREFIX") or "avatars/").strip("/")


def _local_dir() -> Path:
    return Path(os.environ.get("AVATAR_DIR") or settings.FEEDBACK_DIR.parent / "avatars")


def normalize(content: bytes) -> bytes:
    """读图 → 按 EXIF 摆正 → 居中裁成正方形 → 256px JPEG。不是图片或太大时报 415 / 422。"""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(content))
        if image.width * image.height > MAX_PIXELS:
            raise ApiError(422, "图片分辨率过大，请换一张")
        image.load()
        image = ImageOps.exif_transpose(image)
    except ApiError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        raise ApiError(415, "头像只支持 png / jpg / webp 图片") from None
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (251, 249, 244))
        background.paste(image, mask=image.split()[-1])
        image = background
    else:
        image = image.convert("RGB")
    image = ImageOps.fit(image, (SIZE, SIZE), Image.LANCZOS)
    out = io.BytesIO()
    image.save(out, "JPEG", quality=QUALITY, optimize=True)
    return out.getvalue()


def object_key(user: User, data: bytes) -> str:
    """avatars/<用户 id>/<内容摘要>.jpg：内容变了键就变，浏览器缓存不会显示旧头像。"""
    digest = hashlib.sha256(data).hexdigest()[:16]
    return f"{_prefix()}/{user.id}/{digest}.jpg" if _prefix() else f"{user.id}/{digest}.jpg"


def version_of(key: Optional[str]) -> str:
    return Path(key).stem if key else ""


# ---------------------------------------------------------------- 存取（COS / 本地）
def sign(secret_id: str, secret_key: str, method: str, path: str, headers: dict, now: Optional[float] = None) -> str:
    """COS 请求签名（q-sign-algorithm=sha1），与 deploy/cos_upload.py 相同；headers 里每一项都参与签名。"""
    import hmac
    import time
    from urllib.parse import quote

    def enc(value):
        return quote(str(value), safe="-_.~")

    def mac(key, message):
        return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha1).hexdigest()

    start = int(now if now is not None else time.time()) - 60
    key_time = f"{start};{start + 600}"
    items = sorted((enc(k.lower()), enc(v)) for k, v in headers.items())
    header_string = "&".join(f"{k}={v}" for k, v in items)
    http_string = f"{method.lower()}\n{path}\n\n{header_string}\n"
    digest = hashlib.sha1(http_string.encode("utf-8")).hexdigest()
    string_to_sign = f"sha1\n{key_time}\n{digest}\n"
    signature = mac(mac(secret_key, key_time), string_to_sign)
    return (f"q-sign-algorithm=sha1&q-ak={secret_id}&q-sign-time={key_time}&q-key-time={key_time}"
            f"&q-header-list={';'.join(k for k, _ in items)}&q-url-param-list=&q-signature={signature}")


def _cos_request(config: dict, method: str, key: str, data: bytes = b"", connection=None):
    """对 COS 发一个请求，返回 (status, body)。签名与备份脚本相同（deploy/cos_upload.py）。"""
    import base64
    import http.client
    from urllib.parse import quote

    host = f"{config['COS_BUCKET']}.cos.{config['COS_REGION']}.myqcloud.com"
    path = "/" + quote(key, safe="/-_.~")
    headers = {"Host": host}
    if method == "PUT":
        headers.update({"Content-Length": str(len(data)), "Content-Type": "image/jpeg",
                        "Content-MD5": base64.b64encode(hashlib.md5(data).digest()).decode()})
    headers["Authorization"] = sign(config["COS_SECRET_ID"], config["COS_SECRET_KEY"], method, path,
                                    {k: v for k, v in headers.items() if k != "Authorization"})
    conn = connection or http.client.HTTPSConnection(host, timeout=20)
    try:
        conn.request(method, path, body=data if method == "PUT" else None, headers=headers)
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        if connection is None:
            conn.close()


def save(key: str, data: bytes) -> None:
    config = cos_config()
    if config:
        try:
            status, body = _cos_request(config, "PUT", key, data)
        except OSError:
            raise ApiError(502, "头像上传到存储失败，请稍后再试") from None
        if status >= 300:
            raise ApiError(502, "头像上传到存储失败，请稍后再试", {"status": status})
        return
    path = _local_dir() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def load(key: str) -> Optional[bytes]:
    config = cos_config()
    if config:
        try:
            status, body = _cos_request(config, "GET", key)
        except OSError:
            return None
        return body if status == 200 else None
    path = _local_dir() / key
    return path.read_bytes() if path.is_file() else None


def remove(key: Optional[str]) -> None:
    """删掉旧头像；失败不影响主流程（对象留在桶里，桶的生命周期规则会兜底）。"""
    if not key:
        return
    config = cos_config()
    if config:
        try:
            _cos_request(config, "DELETE", key)
        except OSError:
            pass
        return
    path = _local_dir() / key
    try:
        path.unlink()
    except OSError:
        pass
