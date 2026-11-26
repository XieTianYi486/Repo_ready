from __future__ import annotations

from abc import ABC, abstractmethod
from urllib.parse import quote

from ...errors import ScanError
from ...models import CommitInfo, Platform, RepoInfo
from ..http_client import HttpClient, JsonResult, _retry_after
from .parser import ParsedRepo


class PlatformAdapter(ABC):
    platform: Platform
    api_hosts: tuple[str, ...]
    archive_hosts: tuple[str, ...]

    def __init__(self, token: str = "") -> None:
        self.token = token

    @abstractmethod
    def fetch_meta(self, client: HttpClient, parsed: ParsedRepo) -> RepoInfo:
        raise NotImplementedError

    @abstractmethod
    def fetch_head(
        self, client: HttpClient, parsed: ParsedRepo, branch: str
    ) -> CommitInfo:
        raise NotImplementedError

    @abstractmethod
    def archive_url(self, parsed: ParsedRepo, ref: str, *, by_sha: bool) -> str:
        raise NotImplementedError

    def blob_url(
        self, parsed: ParsedRepo, sha: str, path: str, line: int | None = None
    ) -> str:
        encoded_path = quote(path, safe="/")
        url = f"{parsed.html_url}/blob/{sha}/{encoded_path}"
        return f"{url}#L{line}" if line else url

    def tree_url(self, parsed: ParsedRepo, sha: str) -> str:
        return f"{parsed.html_url}/tree/{sha}"

    def commit_url(self, parsed: ParsedRepo, sha: str) -> str:
        return f"{parsed.html_url}/commit/{sha}"

    def api_headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def api_params(self) -> dict[str, str] | None:
        return None

    @staticmethod
    def raise_status(result: JsonResult, *, platform: str) -> None:
        status = result.status
        if status == 200:
            return
        retry_after = _retry_after(result.headers)
        if status in {403, 429}:
            raise ScanError(
                "RATE_LIMITED",
                f"{platform} API 触发限流，请配置 Token 或稍后重试",
                retry_after=retry_after,
                http_status=429,
            )
        if status == 404:
            raise ScanError(
                "REPO_NOT_FOUND",
                "仓库不存在，或不是公开仓库",
                http_status=404,
            )
        if status in {401}:
            raise ScanError(
                "TOKEN_INVALID",
                f"{platform} Token 无效或权限不足",
                http_status=401,
            )
        if status == 451:
            raise ScanError(
                "REPO_UNAVAILABLE",
                "仓库因合规原因不可访问",
                http_status=451,
            )
        raise ScanError(
            "API_ERROR",
            f"{platform} API 返回异常（HTTP {status}）",
            http_status=502,
            retry_after=retry_after,
        )


def safe_branch_ref(branch: str) -> str:
    return quote(branch, safe="")
