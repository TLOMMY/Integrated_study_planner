# -*- coding: utf-8 -*-
"""
模型供应商管理（参考 CC Switch）：每个用户可保存多套 OpenAI 兼容配置并一键切换。

user.ai_provider 取值：
  "auto" —— 使用服务器 .env 中的 DeepSeek（若已配置），否则规则引擎
  "rule" —— 始终使用本地规则引擎
  "<id>" —— 使用该用户保存的某个配置
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.llm import ModelConfig
from app.core import crypto
from app.core.config import settings
from app.models import AiProvider, User

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


def env_config(thinking: str = "high") -> Optional[ModelConfig]:
    if not settings.DEEPSEEK_API_KEY:
        return None
    # 思考模式 + 多步工具调用耗时更长，超时至少 120 秒
    return ModelConfig(base_url=settings.DEEPSEEK_API_URL, api_key=settings.DEEPSEEK_API_KEY,
                       model=env_model(), name=ENV_NAME, source="env",
                       timeout=max(settings.DEEPSEEK_TIMEOUT, 120), thinking=_thinking(thinking))


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
    return env_config(getattr(user, "ai_thinking", None) or "high")


def active_info(db: Session, user: User) -> dict:
    config = resolve(db, user)
    if config is None:
        return {"provider": "rule", "name": "本地规则引擎", "model": None, "label": "本地规则引擎", "source": "rule"}
    thinking = config.thinking if llm.supports_thinking(config) else "off"
    return {"provider": "llm", "name": config.name, "model": config.model,
            "label": f"{config.name} · {config.model}", "source": config.source,
            # thinking_supported=False 时界面上的"思考强度"置灰（该模型不传思考参数）
            "thinking": thinking, "thinking_setting": config.thinking,
            "thinking_supported": llm.supports_thinking(ModelConfig(config.base_url, "", config.model, thinking="high"))}
