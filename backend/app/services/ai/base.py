from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from ...models import AiBlocker, AiQuickWin, AiStep


class AiError(Exception):
    def __init__(self, message: str, *, code: str = "AI_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class AiAdvicePayload(BaseModel):
    summary: str = ""
    reference_score: int | None = None
    score_reason: str = ""
    blockers: list[AiBlocker] = Field(default_factory=list)
    quick_wins: list[AiQuickWin] = Field(default_factory=list)
    integration_plan: list[AiStep] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class AiProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def generate(self, payload: dict[str, Any], *, timeout: int) -> tuple[dict[str, Any], str]:
        """Return (raw_json_dict, actual_model_name)."""
        raise NotImplementedError


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise AiError("AI 未返回有效 JSON", code="AI_INVALID_JSON")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AiError("AI 返回的 JSON 无法解析", code="AI_INVALID_JSON") from exc
    if not isinstance(data, dict):
        raise AiError("AI 返回的数据结构不正确", code="AI_INVALID_JSON")
    return data
