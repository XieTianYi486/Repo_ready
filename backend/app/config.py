from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

TOOL_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
RULES_VERSION = "2026.11.26.1"
FORMULA_VERSION = "score-v1"


def _env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value is None else value.strip()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}


@dataclass
class Settings:
    """Runtime configuration. Secrets are excluded from repr on purpose."""

    base_dir: Path = BASE_DIR
    data_dir: Path = field(default_factory=lambda: BASE_DIR / "data")
    frontend_dist: Path = field(default_factory=lambda: BASE_DIR / "frontend" / "dist")

    host: str = "127.0.0.1"
    port: int = 8000

    github_token: str = field(default="", repr=False)
    gitee_token: str = field(default="", repr=False)

    ai_provider: str = "auto"
    ai_enabled: bool = True
    ai_timeout_seconds: int = 30
    anthropic_api_key: str = field(default="", repr=False)
    anthropic_model: str = "claude-opus-5-5"
    anthropic_base_url: str | None = None
    openai_api_key: str = field(default="", repr=False)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = ""

    max_archive_bytes: int = 50 * 1024 * 1024
    max_extracted_bytes: int = 200 * 1024 * 1024
    max_files: int = 5000
    max_text_file_bytes: int = 512 * 1024
    max_total_text_bytes: int = 20 * 1024 * 1024
    scan_concurrency: int = 2
    scan_timeout_seconds: int = 180
    request_timeout_seconds: int = 60

    rate_limit_per_minute: int = 30
    update_cache_seconds: int = 300
    max_redirects: int = 5
    github_git_fallback: bool = False
    gitee_git_fallback: bool = True
    dev_cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )

    @classmethod
    def load(cls) -> "Settings":
        max_archive_mb = _env_int("MAX_ARCHIVE_MB", 50)
        max_extracted_mb = _env_int("MAX_EXTRACTED_MB", 200)
        anthropic_base = _env_str("ANTHROPIC_BASE_URL")
        openai_base = _env_str("OPENAI_BASE_URL", "https://api.openai.com/v1")
        return cls(
            host=_env_str("HOST", "127.0.0.1"),
            port=_env_int("PORT", 8000),
            github_token=_env_str("GITHUB_TOKEN"),
            gitee_token=_env_str("GITEE_TOKEN"),
            ai_provider=_env_str("AI_PROVIDER", "auto").lower(),
            ai_enabled=_env_bool("AI_ENABLED", True),
            ai_timeout_seconds=_env_int("AI_TIMEOUT_SECONDS", 30),
            anthropic_api_key=_env_str("ANTHROPIC_API_KEY"),
            anthropic_model=_env_str("ANTHROPIC_MODEL", "claude-opus-5-5"),
            anthropic_base_url=anthropic_base or None,
            openai_api_key=_env_str("OPENAI_API_KEY"),
            openai_base_url=openai_base or "https://api.openai.com/v1",
            openai_model=_env_str("OPENAI_MODEL"),
            max_archive_bytes=max_archive_mb * 1024 * 1024,
            max_extracted_bytes=max_extracted_mb * 1024 * 1024,
            max_files=_env_int("MAX_FILES", 5000),
            scan_concurrency=max(1, _env_int("SCAN_CONCURRENCY", 2)),
            rate_limit_per_minute=max(1, _env_int("RATE_LIMIT_PER_MINUTE", 30)),
        )

    def ensure_dirs(self) -> None:
        (self.data_dir / "reports").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "tmp").mkdir(parents=True, exist_ok=True)

    def resolved_ai_provider(self) -> str | None:
        """Return 'anthropic' | 'openai' | None based on provider + credentials."""
        if not self.ai_enabled:
            return None
        provider = (self.ai_provider or "auto").strip().lower()
        if provider in {"off", "none", "disabled", "false"}:
            return None
        if provider == "auto":
            if self.anthropic_api_key:
                return "anthropic"
            if self.openai_api_key and self.openai_model:
                return "openai"
            return None
        if provider == "anthropic":
            return "anthropic" if self.anthropic_api_key else None
        if provider in {"openai", "openai-compatible", "compatible"}:
            return "openai" if (self.openai_api_key and self.openai_model) else None
        return None

    def ai_model(self) -> str:
        provider = self.resolved_ai_provider()
        if provider == "anthropic":
            return self.anthropic_model
        if provider == "openai":
            return self.openai_model
        return ""

    def ai_public_config(self) -> dict[str, object]:
        provider = self.resolved_ai_provider()
        return {
            "enabled": provider is not None,
            "provider": provider,
            "model": self.ai_model() if provider else None,
        }
