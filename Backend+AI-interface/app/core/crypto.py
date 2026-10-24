# -*- coding: utf-8 -*-
"""
敏感配置加密：用户填写的模型 API Key 以 Fernet 加密后入库，密钥由 JWT_SECRET_KEY 派生。
更换 JWT_SECRET_KEY 后旧密文无法解密，decrypt 返回空串，前端会提示重新填写。
"""

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(f"ai-provider-key:{settings.SECRET_KEY}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plain: Optional[str]) -> Optional[str]:
    if not plain:
        return None
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(token: Optional[str]) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""
