from __future__ import annotations

from urllib.parse import quote

from ...models import CommitInfo, RepoInfo
from ..http_client import HttpClient
from .base import PlatformAdapter, safe_branch_ref
from .parser import ParsedRepo


class GitHubAdapter(PlatformAdapter):
    platform = "github"
    api_hosts = ("api.github.com",)
    archive_hosts = ("codeload.github.com", "github.com")

    def api_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def fetch_meta(self, client: HttpClient, parsed: ParsedRepo) -> RepoInfo:
        url = (
            "https://api.github.com/repos/"
            f"{quote(parsed.owner, safe='')}/{quote(parsed.name, safe='')}"
        )
        result = client.get_json(
            url,
            headers=self.api_headers(),
            allowed_hosts=self.api_hosts,
        )
        self.raise_status(result, platform="GitHub")
        data = result.data or {}
        if data.get("private"):
            from ...errors import ScanError

            raise ScanError(
                "PRIVATE_REPO",
                "仅支持公开仓库；该仓库为私有仓库，已拒绝访问",
                http_status=403,
            )
        license_data = data.get("license")
        license_name: str | None
        if isinstance(license_data, dict):
            license_name = license_data.get("spdx_id") or license_data.get("name")
        elif isinstance(license_data, str):
            license_name = license_data
        else:
            license_name = None
        return RepoInfo(
            platform="github",
            owner=parsed.owner,
            name=parsed.name,
            full_name=data.get("full_name") or parsed.full_name,
            html_url=data.get("html_url") or parsed.html_url,
            default_branch=data.get("default_branch") or "main",
            description=data.get("description"),
            stars=int(data.get("stargazers_count") or 0),
            forks=int(data.get("forks_count") or 0),
            language=data.get("language"),
            license=license_name,
            archived=bool(data.get("archived")),
            private=bool(data.get("private")),
            pushed_at=data.get("pushed_at"),
            size_kb=data.get("size"),
        )

    def fetch_head(
        self, client: HttpClient, parsed: ParsedRepo, branch: str
    ) -> CommitInfo:
        url = (
            "https://api.github.com/repos/"
            f"{quote(parsed.owner, safe='')}/{quote(parsed.name, safe='')}"
            f"/branches/{safe_branch_ref(branch)}"
        )
        result = client.get_json(
            url,
            headers=self.api_headers(),
            allowed_hosts=self.api_hosts,
        )
        if result.status == 404:
            from ...errors import ScanError

            raise ScanError(
                "BRANCH_NOT_FOUND",
                f"分支不存在：{branch}",
                http_status=404,
            )
        self.raise_status(result, platform="GitHub")
        data = result.data or {}
        commit = data.get("commit") or {}
        inner = commit.get("commit") or {}
        author = inner.get("author") or {}
        sha = str(commit.get("sha") or "")
        if not sha:
            from ...errors import ScanError

            raise ScanError("API_ERROR", "GitHub 未返回分支的最新提交", http_status=502)
        return CommitInfo(
            sha=sha,
            short_sha=sha[:7],
            branch=branch,
            message=str(inner.get("message") or "").splitlines()[0][:300],
            author=str(author.get("name") or ""),
            date=author.get("date") or inner.get("date"),
            url=self.commit_url(parsed, sha),
            source="api",
            archive_ref="sha",
        )

    def archive_url(self, parsed: ParsedRepo, ref: str, *, by_sha: bool) -> str:
        ref_encoded = quote(ref, safe="")
        return (
            "https://codeload.github.com/"
            f"{quote(parsed.owner, safe='')}/{quote(parsed.name, safe='')}"
            f"/tar.gz/{ref_encoded}"
        )
