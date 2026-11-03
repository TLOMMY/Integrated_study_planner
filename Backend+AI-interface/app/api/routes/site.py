# -*- coding: utf-8 -*-
"""
公开的站点信息（无需登录）——备案号、联系邮箱、隐私政策 / 用户协议版本。

登录页底部、设置「关于」、/privacy、/terms 页面读取。备案号为空时前端不显示。
"""

import re

from fastapi import APIRouter

from app.core.config import settings
from app.core.errors import ok

router = APIRouter(tags=["站点信息"])

MIIT_URL = "https://beian.miit.gov.cn/"
MPS_URL = "https://beian.mps.gov.cn/"


def police_link(number: str) -> str:
    """公安备案号链接：带上号码中的数字可直接打开查询结果。"""
    digits = "".join(re.findall(r"\d+", number or ""))
    return f"{MPS_URL}#/query/webSearch?code={digits}" if digits else MPS_URL


@router.get("/site/info", summary="站点信息：备案号、联系邮箱、隐私政策与用户协议版本（公开）")
def site_info():
    icp = (settings.ICP_NUMBER or "").strip()
    police = (settings.POLICE_BEIAN or "").strip()
    return ok({
        "app_name": "学业管家",
        "version": settings.APP_VERSION,
        "icp_number": icp,
        "icp_url": MIIT_URL if icp else "",
        "police_beian": police,
        "police_url": police_link(police) if police else "",
        "contact_email": (settings.CONTACT_EMAIL or "").strip(),
        "terms_version": settings.TERMS_VERSION,
    })
