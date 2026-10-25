# -*- coding: utf-8 -*-
"""
OpenAI Chat Completions 兼容客户端。

DeepSeek、Kimi、通义千问、智谱 GLM、硅基流动、OpenAI、本地 Ollama / LM Studio 等
都实现了同一套协议：POST {base_url}/chat/completions，Bearer 鉴权。这里只依赖标准库。
"""

import http.client
import ipaddress
import json
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, Generator, Iterator, List, Optional, Tuple
from urllib.parse import urlparse


class LlmError(Exception):
    def __init__(self, message: str, status: Optional[int] = None, detail: str = ""):
        super().__init__(message)
        self.message = message
        self.status = status
        # 服务端返回的原始错误说明（英文居多），用于判断"是否不支持 tools / 思考参数"
        self.detail = detail


# 思考强度：off 不思考；high / max 对应 DeepSeek 的 reasoning_effort
THINKING_LEVELS = ("off", "high", "max")


@dataclass
class ModelConfig:
    base_url: str
    api_key: str
    model: str
    name: str = "自定义模型"
    source: str = "user"  # user / env
    timeout: int = 45
    thinking: str = "high"


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
        detail = _error_detail(error)
        raise LlmError(_http_message(error.code, detail), error.code, detail) from None
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


# ---------------------------------------------------------------- 工具调用 + 流式输出（智能体用）
def supports_thinking(config: ModelConfig) -> bool:
    """
    是否给这次请求加思考参数。目前只有 DeepSeek 的 v4-pro 系列按
    thinking={"type":"enabled"} + reasoning_effort 开启思考；其他模型不传，避免被拒。
    """
    if (config.thinking or "off") == "off":
        return False
    model = (config.model or "").lower()
    return "deepseek" in model and "pro" in model


@dataclass
class StreamResult:
    content: str = ""
    reasoning: str = ""
    tool_calls: Optional[List[dict]] = None
    finish_reason: Optional[str] = None
    usage: Optional[dict] = None


def _open_stream(url: str, api_key: str, body: dict, timeout: int):
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                     headers=headers, method="POST")
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        detail = _error_detail(error)
        raise LlmError(_http_message(error.code, detail), error.code, detail) from None
    except (socket.timeout, TimeoutError):
        raise LlmError("模型响应超时") from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            raise LlmError("模型响应超时") from None
        raise LlmError(f"无法连接接口地址（{error.reason}）") from None


def _iter_lines(response):
    """逐行读取响应体；兼容真实 HTTPResponse（可迭代）与测试替身（只有 read()）。"""
    if hasattr(response, "readline"):
        while True:
            line = response.readline()
            if not line:
                return
            yield line
    yield from response.read().splitlines(keepends=True)


def _merge_tool_delta(slots: Dict[int, dict], deltas) -> None:
    """tool_calls 在流里按 index 分片下发：id / name 只出现一次，arguments 逐段拼接。"""
    for position, delta in enumerate(deltas or []):
        index = delta.get("index", position)
        slot = slots.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
        if delta.get("id"):
            slot["id"] = delta["id"]
        function = delta.get("function") or {}
        if function.get("name"):
            slot["function"]["name"] += function["name"]
        if function.get("arguments"):
            slot["function"]["arguments"] += function["arguments"]


def _apply_message(result: StreamResult, slots: Dict[int, dict], message: dict) -> Iterator[Tuple[str, str]]:
    """非流式响应（或流里出现完整 message）时整段取出。"""
    reasoning = message.get("reasoning_content") or ""
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if reasoning:
        result.reasoning += reasoning
        yield "reasoning", reasoning
    if content:
        result.content += content
        yield "text", content
    for index, call in enumerate(message.get("tool_calls") or []):
        function = call.get("function") or {}
        slots[index] = {"id": call.get("id") or "", "type": "function",
                        "function": {"name": function.get("name") or "", "arguments": function.get("arguments") or ""}}


def stream_chat(config: ModelConfig, messages: List[dict], tools: Optional[List[dict]] = None,
                tool_choice: Optional[str] = None, temperature: float = 0.5,
                max_tokens: Optional[int] = None) -> Generator[Tuple[str, str], None, StreamResult]:
    """
    流式调用（stream=true），边收边产出 ("reasoning", 片段) / ("text", 片段)，结束时 return StreamResult。
    用法：result = yield from stream_chat(...)

    - 思考模式：supports_thinking 时带 thinking + reasoning_effort，返回 reasoning_content；
      服务端不认识这些参数（400/422）时去掉重试一次。
    - 服务端忽略 stream、直接回整段 JSON 时也能解析。
    """
    body = {"model": config.model, "messages": messages, "stream": True, "stream_options": {"include_usage": True}}
    if supports_thinking(config):
        body["thinking"] = {"type": "enabled"}
        body["reasoning_effort"] = "max" if config.thinking == "max" else "high"
    else:
        body["temperature"] = temperature
    if tools:
        body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice
    if max_tokens:
        body["max_tokens"] = max_tokens
    url = chat_url(config.base_url)
    try:
        response = _open_stream(url, config.api_key, body, config.timeout)
    except LlmError as error:
        if error.status not in (400, 422) or tools_unsupported(error, strict=True):
            raise
        # 兼容性重试：去掉思考参数与 stream_options（部分 OpenAI 兼容服务不认识）
        body.pop("thinking", None)
        body.pop("reasoning_effort", None)
        body.pop("stream_options", None)
        body.setdefault("temperature", temperature)
        response = _open_stream(url, config.api_key, body, config.timeout)

    result = StreamResult()
    slots: Dict[int, dict] = {}
    whole: List[str] = []
    try:
        for raw in _iter_lines(response):
            line = (raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else str(raw)).strip()
            if not line or line.startswith(":"):
                continue
            if not line.startswith("data:"):
                whole.append(line)
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            if not isinstance(chunk, dict):
                continue
            if chunk.get("usage"):
                result.usage = chunk["usage"]
            if isinstance(chunk.get("error"), dict):
                raise LlmError(f"模型返回错误：{str(chunk['error'].get('message') or '')[:120]}")
            for choice in chunk.get("choices") or []:
                if choice.get("finish_reason"):
                    result.finish_reason = choice["finish_reason"]
                if isinstance(choice.get("message"), dict):
                    yield from _apply_message(result, slots, choice["message"])
                    continue
                delta = choice.get("delta") or {}
                piece = delta.get("reasoning_content")
                if piece:
                    result.reasoning += piece
                    yield "reasoning", piece
                piece = delta.get("content")
                if piece:
                    result.content += piece
                    yield "text", piece
                if delta.get("tool_calls"):
                    _merge_tool_delta(slots, delta["tool_calls"])
        if whole and not result.content and not slots:
            # 服务端忽略了 stream=true，直接返回了完整 JSON
            try:
                payload = json.loads("\n".join(whole))
                choice = (payload.get("choices") or [{}])[0]
            except (ValueError, AttributeError, IndexError):
                raise LlmError("接口返回格式不符合 OpenAI Chat Completions") from None
            result.finish_reason = choice.get("finish_reason")
            result.usage = payload.get("usage")
            yield from _apply_message(result, slots, choice.get("message") or {})
    except (socket.timeout, TimeoutError):
        raise LlmError("模型响应超时") from None
    except (OSError, http.client.HTTPException) as error:
        # 流读到一半连接被重置 / 不完整的分块响应；status=None，调用方可按网络抖动重试
        raise LlmError(f"与模型服务的连接中断（{type(error).__name__}）") from None
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()
    calls = [slots[i] for i in sorted(slots) if slots[i]["function"]["name"]]
    for position, call in enumerate(calls):
        call["id"] = call["id"] or f"call_{position}"
    result.tool_calls = calls or None
    return result


def tools_unsupported(error: LlmError, strict: bool = False) -> bool:
    """
    模型 / 服务不支持工具调用（400/422 且错误说明里提到 tool / function）。
    strict=False 时，没有错误说明的 400/422 也按"不支持"处理，由调用方降级为 JSON 草稿流程。
    """
    if error.status not in (400, 422):
        return False
    detail = (error.detail or "").lower()
    if not detail:
        return not strict
    return any(key in detail for key in ("tool", "function"))
