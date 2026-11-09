# -*- coding: utf-8 -*-
"""
模型供应商管理（参考 CC Switch）：每个用户可保存多套 OpenAI 兼容配置并一键切换。

user.ai_provider 取值：
  "auto" —— 使用服务器 .env 中的 DeepSeek（若已配置），否则规则引擎
  "rule" —— 始终使用本地规则引擎
  "<id>" —— 使用该用户保存的某个配置
"""

import dataclasses
from typing import List, Optional

from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.llm import ModelConfig
from app.core import crypto
from app.core.config import settings
from app.models import AiProvider, User
from app.services import ai_quota

PRESETS: List[dict] = [
    {"key": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-v4-pro",
     "needs_key": True, "hint": "platform.deepseek.com 创建 Key；deepseek-v4-pro 支持思考模式与工具调用"},
    {"key": "kimi", "name": "Kimi 月之暗面", "base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k",
     "needs_key": True, "hint": "platform.moonshot.cn 创建 Key"},
    {"key": "qwen", "name": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "model": "qwen-plus", "needs_key": True, "hint": "阿里云百炼控制台创建 Key"},
    {"key": "glm", "name": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash",
     "needs_key": True, "hint": "open.bigmodel.cn 创建 Key"},
    {"key": "siliconflow", "name": "硅基流动", "base_url": "https://api.siliconflow.cn/v1",
     "model": "Qwen/Qwen2.5-7B-Instruct", "needs_key": True, "hint": "cloud.siliconflow.cn 创建 Key"},
    {"key": "openai", "name": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini",
     "needs_key": True, "hint": "platform.openai.com 创建 Key"},
    {"key": "ollama", "name": "Ollama 本地", "base_url": "http://localhost:11434/v1", "model": "qwen2.5:7b",
     "needs_key": False, "hint": "本机运行 ollama serve，无需 Key"},
    {"key": "custom", "name": "自定义", "base_url": "", "model": "", "needs_key": False,
     "hint": "任何兼容 OpenAI /v1/chat/completions 的服务"},
]

ENV_NAME = "DeepSeek（服务器配置）"

# DeepSeek 旧模型名现在都是不思考的 deepseek-flash 别名；服务器配置沿用旧默认值时升级到 v4-pro
LEGACY_ENV_MODELS = {"deepseek-chat", "deepseek-reasoner"}
DEFAULT_ENV_MODEL = "deepseek-v4-pro"

THINKING_LABELS = {"off": "关闭", "high": "高", "max": "最高"}


def _thinking(value) -> str:
    return value if value in llm.THINKING_LEVELS else "high"


def mask_key(key: str) -> str:
    if not key:
        return ""
    return f"{key[:3]}****{key[-4:]}" if len(key) > 10 else "****"


def provider_to_dict(provider: AiProvider, active: str) -> dict:
    key = crypto.decrypt(provider.api_key_enc)
    return {
        "id": provider.id,
        "name": provider.name,
        "base_url": provider.base_url,
        "model": provider.model,
        "has_key": bool(key),
        "key_masked": mask_key(key),
        "key_unreadable": bool(provider.api_key_enc) and not key,
        "active": active == str(provider.id),
        "thinking": _thinking(provider.thinking),
        "created_at": provider.created_at.isoformat() if provider.created_at else None,
    }


def env_model() -> str:
    model = settings.DEEPSEEK_MODEL or DEFAULT_ENV_MODEL
    return DEFAULT_ENV_MODEL if model in LEGACY_ENV_MODELS else model


# ---- 模型友好名、服务器 DeepSeek 下可选 Flash / Pro
FAST_ENV_MODEL = "deepseek-flash"
ENV_MODELS: List[dict] = [
    {"key": "deepseek-flash", "label": "DeepSeek V4.1 Flash（快）",
     "hint": "响应快、省额度，日常问答、排任务、课表识别都够用"},
    {"key": "deepseek-v4-pro", "label": "DeepSeek V4 Pro（强）",
     "hint": "推理更强，复杂规划和多步修改更稳，但更慢"},
]
MODEL_LABELS = {item["key"]: item["label"] for item in ENV_MODELS}


def model_label(model: Optional[str]) -> str:
    """界面显示用的模型名：deepseek-flash → DeepSeek V4.1 Flash（快），其余原样。"""
    return MODEL_LABELS.get((model or "").strip().lower(), model or "")


def env_model_choice(user: Optional[User]) -> Optional[str]:
    """用户在 AI 设置里为服务器 DeepSeek 选的模型；没选（或值不认识）返回 None。"""
    value = getattr(user, "ai_env_model", None) if user is not None else None
    return value if value in MODEL_LABELS else None


def env_config(thinking: str = "high", model: Optional[str] = None) -> Optional[ModelConfig]:
    if not settings.DEEPSEEK_API_KEY:
        return None
    # 思考模式 + 多步工具调用耗时更长，超时至少 120 秒
    return ModelConfig(base_url=settings.DEEPSEEK_API_URL, api_key=settings.DEEPSEEK_API_KEY,
                       model=model if model in MODEL_LABELS else env_model(), name=ENV_NAME, source="env",
                       timeout=max(settings.DEEPSEEK_TIMEOUT, 120), thinking=_thinking(thinking))


VISION_ENV_NAME = "豆包（服务器配置）"


def vision_env_config(user: Optional[User] = None) -> Optional[ModelConfig]:
    """服务器的视觉模型（豆包）。没配置时返回 None。和服务器 DeepSeek 一样计入每日 AI 额度。"""
    if not settings.ARK_API_KEY or not settings.ARK_MODEL:
        return None
    config = ModelConfig(base_url=settings.ARK_BASE_URL, api_key=settings.ARK_API_KEY, model=settings.ARK_MODEL,
                         name=VISION_ENV_NAME, source="env", timeout=max(settings.AI_TIMEOUT, 120), thinking="off")
    return ai_quota.attach(config, user) if user is not None else config


def to_config(provider: AiProvider) -> ModelConfig:
    return ModelConfig(base_url=provider.base_url, api_key=crypto.decrypt(provider.api_key_enc),
                       model=provider.model, name=provider.name, source="user",
                       timeout=max(settings.AI_TIMEOUT, 120), thinking=_thinking(provider.thinking))


def get_owned(db: Session, user: User, provider_id: int) -> Optional[AiProvider]:
    return db.query(AiProvider).filter(AiProvider.id == provider_id, AiProvider.user_id == user.id).first()


def resolve(db: Session, user: User) -> Optional[ModelConfig]:
    """返回本次应使用的模型配置；None 表示使用规则引擎。"""
    mode = user.ai_provider or "auto"
    if mode == "rule":
        return None
    if mode.isdigit():
        provider = get_owned(db, user, int(mode))
        if provider is not None:
            return to_config(provider)
    # 服务器 Key 打上用量计数凭据（超额在真正调用模型时返回 429，见 app/services/ai_quota.py）
    return ai_quota.attach(env_config(getattr(user, "ai_thinking", None) or "high", env_model_choice(user)), user)


def extraction_config(config: Optional[ModelConfig], user: Optional[User] = None) -> Optional[ModelConfig]:
    """
    结构化抽取（课表识别等）用的配置：服务器 DeepSeek 且用户没有明确选 Pro 时换成 Flash——
    关闭思考后两者识别结果一致，Flash 快近一倍。用户自己的模型原样使用。
    """
    if config is None or config.source != "env" or env_model_choice(user):
        return config
    return dataclasses.replace(config, model=FAST_ENV_MODEL)


def active_info(db: Session, user: User) -> dict:
    config = resolve(db, user)
    if config is None:
        return {"provider": "rule", "name": "本地规则引擎", "model": None, "label": "本地规则引擎", "source": "rule"}
    thinking = config.thinking if llm.supports_thinking(config) else "off"
    return {"provider": "llm", "name": config.name, "model": config.model,
            "model_label": model_label(config.model),
            "label": f"{config.name} · {model_label(config.model)}", "source": config.source,
            # thinking_supported=False 时界面上的"思考强度"置灰（该模型不传思考参数）
            "thinking": thinking, "thinking_setting": config.thinking,
            "thinking_supported": llm.supports_thinking(ModelConfig(config.base_url, "", config.model, thinking="high")),
            # 服务器 Key 的今日额度（用户自己的 Key 为 None，不限）
            "quota": ai_quota.status(db, user) if config.source == "env" else None}
