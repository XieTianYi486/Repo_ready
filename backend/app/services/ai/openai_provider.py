from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

import httpx

from ...config import Settings
from .base import AiError, AiProvider, parse_json_response
from .prompts import AI_SCHEMA_HINT, AI_SYSTEM_PROMPT


class OpenAICompatibleProvider(AiProvider):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = settings.openai_model

    def _endpoint(self) -> str:
        base = (self.settings.openai_base_url or "").rstrip("/")
        parts = urlsplit(base)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise AiError("OPENAI_BASE_URL 配置不合法", code="AI_CONFIG")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"

    def generate(self, payload: dict[str, Any], *, timeout: int) -> tuple[dict[str, Any], str]:
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": AI_SYSTEM_PROMPT + AI_SCHEMA_HINT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "max_tokens": 3000,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        endpoint = self._endpoint()
        try:
            with httpx.Client(timeout=float(timeout)) as client:
                response = client.post(endpoint, headers=headers, json=body)
                if response.status_code == 400:
                    # Some compatible gateways do not support response_format.
                    body.pop("response_format", None)
                    response = client.post(endpoint, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise AiError("AI 请求超时，请稍后重试", code="AI_TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise AiError("无法连接 OpenAI 兼容接口，请检查 Base URL", code="AI_NETWORK") from exc

        if response.status_code in {401, 403}:
            raise AiError("AI API Key 无效或权限不足", code="AI_AUTH")
        if response.status_code == 429:
            raise AiError("AI 服务触发限流，请稍后重试", code="AI_RATE_LIMITED")
        if response.status_code >= 400:
            raise AiError(f"AI 服务返回异常（HTTP {response.status_code}）", code="AI_HTTP")
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AiError("AI 返回结构不符合预期", code="AI_INVALID_RESPONSE") from exc
        return parse_json_response(str(content)), str(data.get("model") or self.model)
