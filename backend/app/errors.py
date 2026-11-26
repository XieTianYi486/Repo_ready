from __future__ import annotations

from typing import Any


class ScanError(Exception):
    """A user-facing, typed scan error.

    Codes are stable and consumed by the frontend.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: str | None = None,
        retry_after: int | None = None,
        http_status: int = 400,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.retry_after = retry_after
        self.http_status = http_status
        self.extra = extra or {}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error_code": self.code,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        if self.retry_after is not None:
            payload["retry_after"] = self.retry_after
        if self.extra:
            payload.update(self.extra)
        return payload
