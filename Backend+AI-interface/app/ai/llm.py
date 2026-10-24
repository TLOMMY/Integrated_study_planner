# -*- coding: utf-8 -*-
"""
OpenAI Chat Completions 兼容客户端。

DeepSeek、Kimi、通义千问、智谱 GLM、硅基流动、OpenAI、本地 Ollama / LM Studio 等
都实现了同一套协议：POST {base_url}/chat/completions，Bearer 鉴权。这里只依赖标准库。
"""

import ipaddress
import json
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse


class LlmError(Exception):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class ModelConfig:
    base_url: str
    api_key: str
    model: str
    name: str = "自定义模型"
    source: str = "user"  # user / env
    timeout: int = 45


def _strip_endpoint(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    for suffix in ("/chat/completions", "/models"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base


def chat_url(base_url: str) -> str:
    return _strip_endpoint(base_url) + "/chat/completions"


def models_url(base_url: str) -> str:
    return _strip_endpoint(base_url) + "/models"


def validate_base_url(url: str, allow_private: bool = True) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise LlmError("接口地址需以 http:// 或 https:// 开头")
    if not allow_private:
        host = parsed.hostname
        if host == "localhost":
            raise LlmError("当前部署不允许访问本机或内网地址")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
        if ip and (ip.is_private or ip.is_loopback or ip.is_link_local):
            raise LlmError("当前部署不允许访问本机或内网地址")
    return url.strip()


def _error_detail(error: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(error.read().decode("utf-8", "ignore"))
        detail = payload.get("error", payload)
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("msg") or ""
        return str(detail)[:200]
    except Exception:  # noqa: BLE001 - 错误体格式各家不同
        return ""


def _http_message(code: int, detail: str) -> str:
    if code in (401, 403):
        return "API Key 无效或没有权限"
    if code == 404:
        return "接口地址或模型名称不存在"
    if code == 429:
        return "调用过于频繁或账户额度不足"
    if code >= 500:
        return "模型服务暂时不可用"
    return f"请求被拒绝（{code}）{('：' + detail) if detail else ''}"


def _request(method: str, url: str, api_key: str, body: Optional[dict], timeout: int) -> dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise LlmError(_http_message(error.code, _error_detail(error)), error.code) from None
    except (socket.timeout, TimeoutError):
        raise LlmError("模型响应超时") from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            raise LlmError("模型响应超时") from None
        raise LlmError(f"无法连接接口地址（{error.reason}）") from None
    except (ValueError, UnicodeDecodeError):
        raise LlmError("接口返回的不是 JSON，请确认地址是 OpenAI 兼容接口") from None


def chat(config: ModelConfig, messages: List[dict], json_mode: bool = False, temperature: float = 0.4,
         max_tokens: Optional[int] = None) -> str:
    body = {"model": config.model, "messages": messages, "temperature": temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    url = chat_url(config.base_url)
    try:
        data = _request("POST", url, config.api_key, body, config.timeout)
    except LlmError as error:
        # 部分兼容服务不支持 response_format，去掉后重试一次；提示词本身已要求输出 JSON
        if not (json_mode and error.status in (400, 422)):
            raise
        body.pop("response_format")
        data = _request("POST", url, config.api_key, body, config.timeout)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise LlmError("接口返回格式不符合 OpenAI Chat Completions") from None
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content or "")


def extract_json(text: str) -> dict:
    """从模型输出中取出第一个 JSON 对象：兼容 ```json 代码块、<think> 推理段、前后多余文字。"""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except ValueError:
        pass
    start = text.find("{")
    while start != -1:
        depth, in_string, escaped = 0, False, False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(text[start:index + 1])
                        if isinstance(value, dict):
                            return value
                    except ValueError:
                        pass
                    break
        start = text.find("{", start + 1)
    raise LlmError("模型没有返回可解析的 JSON")


def chat_json(config: ModelConfig, messages: List[dict], temperature: float = 0.4) -> dict:
    return extract_json(chat(config, messages, json_mode=True, temperature=temperature))


def ping(config: ModelConfig) -> dict:
    started = time.perf_counter()
    reply = chat(config, [{"role": "user", "content": "请只回复：OK"}], temperature=0, max_tokens=16)
    return {"latency_ms": round((time.perf_counter() - started) * 1000), "reply": reply.strip()[:60]}


def list_models(config: ModelConfig) -> List[str]:
    data = _request("GET", models_url(config.base_url), config.api_key, None, min(config.timeout, 15))
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise LlmError("该接口不支持获取模型列表，请手动填写模型名")
    return sorted({str(item["id"]) for item in items if isinstance(item, dict) and item.get("id")})
