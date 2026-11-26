from __future__ import annotations

import json
import logging
from typing import Any

from ...config import Settings
from .base import AiError, AiProvider, parse_json_response
from .prompts import AI_JSON_SCHEMA, AI_SCHEMA_HINT, AI_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class AnthropicProvider(AiProvider):
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = settings.anthropic_model or "claude-opus-5-5"

    def _client(self, timeout: int):
        try:
            import anthropic
        except ImportError as exc:
            raise AiError(
                "未安装 anthropic SDK，请执行 pip install anthropic",
                code="AI_SDK_MISSING",
            ) from exc
        kwargs: dict[str, Any] = {
            "api_key": self.settings.anthropic_api_key,
            "timeout": float(timeout),
            "max_retries": 0,
        }
        if self.settings.anthropic_base_url:
            kwargs["base_url"] = self.settings.anthropic_base_url
        return anthropic, anthropic.Anthropic(**kwargs)

    @staticmethod
    def _text(response: Any) -> str:
        texts = []
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", "") == "text":
                texts.append(getattr(block, "text", "") or "")
        return "\n".join(texts)

    def _check_refusal(self, response: Any) -> None:
        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            reason = getattr(details, "category", None) if details else None
            raise AiError(
                f"AI 因安全策略拒绝生成建议（{reason or 'refusal'}）",
                code="AI_REFUSAL",
            )

    def generate(self, payload: dict[str, Any], *, timeout: int) -> tuple[dict[str, Any], str]:
        anthropic, client = self._client(timeout)
        system = AI_SYSTEM_PROMPT
        user = json.dumps(payload, ensure_ascii=False)
        try:
            # Preferred: structured output + server-side refusal fallback.
            try:
                response = client.beta.messages.create(
                    model=self.model,
                    max_tokens=3000,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                    thinking={"type": "adaptive"},
                    output_config={
                        "effort": "medium",
                        "format": {"type": "json_schema", "schema": AI_JSON_SCHEMA},
                    },
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
                self._check_refusal(response)
                return parse_json_response(self._text(response)), self.model
            except AiError:
                raise
            except TypeError:
                pass
            except anthropic.BadRequestError:
                pass

            # Fallback 1: no server-side fallback / beta params.
            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=3000,
                    system=system + AI_SCHEMA_HINT,
                    messages=[{"role": "user", "content": user}],
                    output_config={
                        "format": {"type": "json_schema", "schema": AI_JSON_SCHEMA}
                    },
                )
                self._check_refusal(response)
                return parse_json_response(self._text(response)), self.model
            except AiError:
                raise
            except anthropic.BadRequestError:
                pass

            # Fallback 2: plain request; JSON is parsed leniently.
            response = client.messages.create(
                model=self.model,
                max_tokens=3000,
                system=system + AI_SCHEMA_HINT,
                messages=[{"role": "user", "content": user}],
            )
            self._check_refusal(response)
            return parse_json_response(self._text(response)), self.model
        except AiError:
            raise
        except anthropic.AuthenticationError as exc:
            raise AiError("Anthropic API Key 无效或已失效", code="AI_AUTH") from exc
        except anthropic.PermissionDeniedError as exc:
            raise AiError("Anthropic API Key 权限不足", code="AI_AUTH") from exc
        except anthropic.RateLimitError as exc:
            raise AiError("AI 服务触发限流，请稍后重试", code="AI_RATE_LIMITED") from exc
        except anthropic.APITimeoutError as exc:
            raise AiError("AI 请求超时，请稍后重试", code="AI_TIMEOUT") from exc
        except anthropic.APIConnectionError as exc:
            raise AiError("无法连接 Anthropic API，请检查网络或 Base URL", code="AI_NETWORK") from exc
        except anthropic.APIStatusError as exc:
            logger.warning("Anthropic API error: %s", exc.status_code)
            raise AiError(
                f"AI 服务返回异常（HTTP {exc.status_code}）",
                code="AI_HTTP",
            ) from exc
        finally:
            try:
                client.close()
            except Exception:
                pass
