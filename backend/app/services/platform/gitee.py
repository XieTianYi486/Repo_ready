from __future__ import annotations

from urllib.parse import quote

from ...errors import ScanError
from ...models import CommitInfo, RepoInfo
from ..http_client import HttpClient
from .base import PlatformAdapter, TreeEntry, TreeResult, safe_branch_ref
from .parser import ParsedRepo


class GiteeAdapter(PlatformAdapter):
    platform = "gitee"
    api_hosts = ("gitee.com", "www.gitee.com")
    archive_hosts = ("gitee.com", "www.gitee.com")
    raw_hosts = ("gitee.com", "www.gitee.com", "raw.giteeusercontent.com")

    def api_params(self) -> dict[str, str] | None:
        return {"access_token": self.token} if self.token else None

    def api_headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def fetch_meta(self, client: HttpClient, parsed: ParsedRepo) -> RepoInfo:
        url = (
            "https://gitee.com/api/v5/repos/"
            f"{quote(parsed.owner, safe='')}/{quote(parsed.name, safe='')}"
        )
        result = client.get_json(
            url,
            headers=self.api_headers(),
            params=self.api_params(),
            allowed_hosts=self.api_hosts,
        )
        self.raise_status(result, platform="Gitee")
        data = result.data or {}
        if data.get("private"):
            raise ScanError(
                "PRIVATE_REPO",
                "仅支持公开仓库；该仓库为私有仓库，已拒绝访问",
                http_status=403,
            )
        license_data = data.get("license")
        if isinstance(license_data, dict):
            license_name = license_data.get("name") or license_data.get("spdx_id")
        elif isinstance(license_data, str):
            license_name = license_data
        else:
            license_name = None
        return RepoInfo(
            platform="gitee",
            owner=parsed.owner,
            name=parsed.name,
            full_name=data.get("full_name") or parsed.full_name,
            html_url=parsed.html_url,
            default_branch=data.get("default_branch") or "master",
            description=data.get("description"),
            stars=int(data.get("stargazers_count") or 0),
            forks=int(data.get("forks_count") or 0),
            language=data.get("language"),
            license=license_name,
            archived=bool(data.get("archived")),
            private=bool(data.get("private")),
            pushed_at=data.get("pushed_at") or data.get("updated_at"),
            size_kb=None,
        )

    def fetch_head(
        self, client: HttpClient, parsed: ParsedRepo, branch: str
    ) -> CommitInfo:
        url = (
            "https://gitee.com/api/v5/repos/"
            f"{quote(parsed.owner, safe='')}/{quote(parsed.name, safe='')}"
            f"/branches/{safe_branch_ref(branch)}"
        )
        result = client.get_json(
            url,
            headers=self.api_headers(),
            params=self.api_params(),
            allowed_hosts=self.api_hosts,
        )
        if result.status == 404:
            raise ScanError(
                "BRANCH_NOT_FOUND",
                f"分支不存在：{branch}",
                http_status=404,
            )
        self.raise_status(result, platform="Gitee")
        data = result.data or {}
        commit = data.get("commit") or {}
        inner = commit.get("commit") or {}
        author = inner.get("author") or {}
        sha = str(commit.get("sha") or "")
        if not sha:
            raise ScanError("API_ERROR", "Gitee 未返回分支的最新提交", http_status=502)
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
            "https://gitee.com/"
            f"{quote(parsed.owner, safe='')}/{quote(parsed.name, safe='')}"
            f"/repository/archive/{ref_encoded}.zip"
        )

    def fetch_tree(
        self, client: HttpClient, parsed: ParsedRepo, sha: str
    ) -> TreeResult:
        url = (
            "https://gitee.com/api/v5/repos/"
            f"{quote(parsed.owner, safe='')}/{quote(parsed.name, safe='')}"
            f"/git/trees/{quote(sha, safe='')}"
        )
        result = client.get_json(
            url,
            headers=self.api_headers(),
            params={**({"access_token": self.token} if self.token else {}), "recursive": "1"},
            allowed_hosts=self.api_hosts,
        )
        self.raise_status(result, platform="Gitee")
        data = result.data or {}
        entries = []
        for item in data.get("tree") or []:
            if item.get("type") != "blob":
                continue
            entries.append(
                TreeEntry(
                    path=str(item.get("path") or ""),
                    type="blob",
                    size=int(item.get("size") or 0),
                    sha=str(item.get("sha") or ""),
                    mode=str(item.get("mode") or ""),
                )
            )
        return TreeResult(entries=entries, truncated=bool(data.get("truncated")))

    def raw_url(self, parsed: ParsedRepo, sha: str, path: str) -> str:
        return (
            "https://gitee.com/"
            f"{quote(parsed.owner, safe='')}/{quote(parsed.name, safe='')}/raw/"
            f"{quote(sha, safe='')}/{quote(path, safe='/')}"
        )
