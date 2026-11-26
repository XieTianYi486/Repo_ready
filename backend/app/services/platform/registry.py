from __future__ import annotations

from ...models import Platform
from .base import PlatformAdapter
from .gitee import GiteeAdapter
from .github import GitHubAdapter


def get_adapter(platform: Platform, *, github_token: str = "", gitee_token: str = "") -> PlatformAdapter:
    if platform == "github":
        return GitHubAdapter(token=github_token)
    if platform == "gitee":
        return GiteeAdapter(token=gitee_token)
    raise ValueError(f"Unsupported platform: {platform}")
