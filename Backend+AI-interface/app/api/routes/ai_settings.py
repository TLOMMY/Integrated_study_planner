# -*- coding: utf-8 -*-
"""
AI 模型设置（参考 CC Switch）：保存多套 OpenAI 兼容配置、一键切换、测试连接、拉取模型列表。
API Key 加密入库，接口只返回脱敏后的 sk-****abcd。
"""

from fastapi import APIRouter

from app.ai import llm, providers
from app.api.deps import DB, CurrentUser
from app.core import crypto
from app.core.config import settings
from app.core.errors import ApiError, ok
from app.models import AiProvider, User
from app.schemas import AiProbeIn, AiProviderIn, AiProviderUpdateIn, AiSettingsIn

router = APIRouter(prefix="/ai", tags=["AI 模型设置"])

MAX_PROVIDERS = 10


def _settings_payload(db, user: User) -> dict:
    active = user.ai_provider or "auto"
    items = db.query(AiProvider).filter(AiProvider.user_id == user.id).order_by(AiProvider.id).all()
    env = providers.env_config()
    return {
        "active": active,
        "resolved": providers.active_info(db, user),
        "env": {"configured": env is not None, "name": providers.ENV_NAME,
                "model": env.model if env else None},
        "providers": [providers.provider_to_dict(p, active) for p in items],
        "presets": providers.PRESETS,
        "allow_private_urls": settings.AI_ALLOW_PRIVATE_URLS,
    }


def _check_url(url: str) -> str:
    try:
        return llm.validate_base_url(url, settings.AI_ALLOW_PRIVATE_URLS)
    except llm.LlmError as error:
        raise ApiError(422, error.message)


def _owned(db, user: User, provider_id: int) -> AiProvider:
    provider = providers.get_owned(db, user, provider_id)
    if provider is None:
        raise ApiError(404, "模型配置不存在或已被删除")
    return provider


@router.get("/settings", summary="模型设置：当前选择、已保存配置、预设")
def get_settings(user: CurrentUser, db: DB):
    return ok(_settings_payload(db, user))


@router.put("/settings", summary="切换使用的模型：auto / rule / 配置 id")
def update_settings(payload: AiSettingsIn, user: CurrentUser, db: DB):
    if payload.active.isdigit():
        _owned(db, user, int(payload.active))
    user.ai_provider = payload.active
    db.commit()
    return ok(_settings_payload(db, user), "已切换模型")


@router.post("/providers", summary="新增模型配置（OpenAI 兼容）")
def create_provider(payload: AiProviderIn, user: CurrentUser, db: DB):
    if db.query(AiProvider).filter(AiProvider.user_id == user.id).count() >= MAX_PROVIDERS:
        raise ApiError(422, f"最多保存 {MAX_PROVIDERS} 套配置")
    provider = AiProvider(user_id=user.id, name=payload.name, base_url=_check_url(payload.base_url),
                          model=payload.model, api_key_enc=crypto.encrypt(payload.api_key))
    db.add(provider)
    db.flush()
    # 新增后直接启用，和 CC Switch 一样"加完即用"
    user.ai_provider = str(provider.id)
    db.commit()
    return ok(_settings_payload(db, user), "已添加并启用")


@router.put("/providers/{provider_id}", summary="修改模型配置（不传 api_key 则保留原 Key）")
def update_provider(provider_id: int, payload: AiProviderUpdateIn, user: CurrentUser, db: DB):
    provider = _owned(db, user, provider_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("name"):
        provider.name = changes["name"]
    if changes.get("base_url"):
        provider.base_url = _check_url(changes["base_url"])
    if changes.get("model"):
        provider.model = changes["model"]
    if "api_key" in changes and changes["api_key"] is not None:
        provider.api_key_enc = crypto.encrypt(changes["api_key"])
    db.commit()
    return ok(_settings_payload(db, user), "已保存")


@router.delete("/providers/{provider_id}", summary="删除模型配置")
def delete_provider(provider_id: int, user: CurrentUser, db: DB):
    provider = _owned(db, user, provider_id)
    if user.ai_provider == str(provider.id):
        user.ai_provider = "auto"
    db.delete(provider)
    db.commit()
    return ok(_settings_payload(db, user), "已删除")


def _probe_config(db, user: User, payload: AiProbeIn) -> llm.ModelConfig:
    """表单里填了什么就测什么；没填 Key 时沿用已保存配置的 Key。"""
    saved = None
    if payload.provider_id == "env":
        env = providers.env_config()
        if env is None:
            raise ApiError(422, "服务器未配置 DEEPSEEK_API_KEY")
        return env
    if payload.provider_id and payload.provider_id.isdigit():
        saved = providers.to_config(_owned(db, user, int(payload.provider_id)))
    base_url = payload.base_url or (saved.base_url if saved else "")
    if not base_url:
        raise ApiError(422, "请填写接口地址")
    api_key = payload.api_key if payload.api_key else (saved.api_key if saved else "")
    return llm.ModelConfig(base_url=_check_url(base_url), api_key=api_key,
                           model=payload.model or (saved.model if saved else ""),
                           name=saved.name if saved else "测试", timeout=min(settings.AI_TIMEOUT, 20))


@router.post("/providers/test", summary="测试连接：发送一条最短消息，返回延迟")
def test_provider(payload: AiProbeIn, user: CurrentUser, db: DB):
    config = _probe_config(db, user, payload)
    if not config.model:
        raise ApiError(422, "请填写模型名称")
    try:
        result = llm.ping(config)
    except llm.LlmError as error:
        raise ApiError(400, f"连接失败：{error.message}")
    return ok(result, f"连接成功，耗时 {result['latency_ms']} ms")


@router.post("/providers/models", summary="获取该接口可用的模型列表（GET /models）")
def provider_models(payload: AiProbeIn, user: CurrentUser, db: DB):
    config = _probe_config(db, user, payload)
    try:
        models = llm.list_models(config)
    except llm.LlmError as error:
        raise ApiError(400, error.message)
    return ok({"models": models[:200]}, f"共 {len(models)} 个模型")
