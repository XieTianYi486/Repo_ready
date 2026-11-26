from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from ...errors import ScanError
from ...models import Platform

HOST_PLATFORM = {
    "github.com": "github",
    "www.github.com": "github",
    "gitee.com": "gitee",
    "www.gitee.com": "gitee",
}
CANONICAL_HOST = {"github": "github.com", "gitee": "gitee.com"}
OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
SSH_RE = re.compile(
    r"^(?:ssh://)?git@(?P<host>github\.com|gitee\.com)[:/](?P<owner>[^/]+)/(?P<repo>[^\s]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedRepo:
    platform: Platform
    owner: str
    name: str
    branch: str | None
    html_url: str
    repo_key: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


def _validate_branch(branch: str | None) -> str | None:
    if not branch:
        return None
    branch = unquote(branch).strip()
    if not branch:
        return None
    if len(branch) > 120:
        raise ScanError("INVALID_URL", "分支名过长", http_status=400)
    if any(ch.isspace() for ch in branch) or any(ord(ch) < 32 for ch in branch):
        raise ScanError("INVALID_URL", "分支名包含非法字符", http_status=400)
    if ".." in branch or branch.startswith("/") or branch.endswith("/"):
        raise ScanError("INVALID_URL", "分支名包含非法路径片段", http_status=400)
    if any(token in branch for token in ("~", "^", ":", "?", "*", "[", "\\")):
        raise ScanError("INVALID_URL", "分支名包含 Git 不支持的字符", http_status=400)
    return branch


def _normalize_raw(raw: str) -> str:
    value = (raw or "").strip().strip("'\"")
    if not value:
        raise ScanError("INVALID_URL", "请输入公开仓库链接", http_status=400)
    if value.startswith("git@"):
        match = SSH_RE.match(value)
        if not match:
            raise ScanError("INVALID_URL", "无法识别的 SSH 仓库地址", http_status=400)
        host = match.group("host").lower()
        platform = HOST_PLATFORM.get(host)
        if not platform:
            raise ScanError(
                "UNSUPPORTED_PLATFORM",
                "目前仅支持 GitHub 与 Gitee 公开仓库",
                http_status=400,
            )
        return (
            f"https://{CANONICAL_HOST[platform]}/"
            f"{match.group('owner')}/{match.group('repo')}"
        )
    if "://" not in value:
        value = "https://" + value
    return value


def parse_repo_url(raw: str, branch_override: str | None = None) -> ParsedRepo:
    value = _normalize_raw(raw)
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise ScanError("INVALID_URL", "仓库链接格式不正确", http_status=400) from exc

    if parts.scheme.lower() not in {"http", "https"}:
        raise ScanError("INVALID_URL", "仅支持 HTTP/HTTPS 仓库链接", http_status=400)
    if parts.username or parts.password:
        raise ScanError("INVALID_URL", "链接中不允许包含用户信息", http_status=400)
    try:
        port = parts.port
    except ValueError as exc:
        raise ScanError("INVALID_URL", "仓库链接端口格式不正确", http_status=400) from exc
    if port not in (None, 80, 443):
        raise ScanError("INVALID_URL", "链接中不允许使用非标准端口", http_status=400)

    host = (parts.hostname or "").lower()
    platform = HOST_PLATFORM.get(host)
    if not platform:
        raise ScanError(
            "UNSUPPORTED_PLATFORM",
            "目前仅支持 github.com 与 gitee.com 的公开仓库",
            http_status=400,
        )

    segments = [unquote(segment) for segment in parts.path.split("/") if segment]
    if len(segments) < 2:
        raise ScanError(
            "INVALID_URL",
            "链接需要包含仓库的 owner/repo，例如 https://github.com/owner/repo",
            http_status=400,
        )

    owner, name = segments[0], segments[1]
    if name.lower().endswith(".git"):
        name = name[:-4]
    if not OWNER_REPO_RE.match(owner) or not OWNER_REPO_RE.match(name):
        raise ScanError("INVALID_URL", "仓库 owner 或名称包含非法字符", http_status=400)
    if owner in {".", ".."} or name in {".", ".."}:
        raise ScanError("INVALID_URL", "仓库路径不合法", http_status=400)

    branch = _validate_branch(branch_override)
    if branch is None and len(segments) >= 4 and segments[2] == "tree":
        branch = _validate_branch(segments[3])

    canonical_host = CANONICAL_HOST[platform]
    html_url = f"https://{canonical_host}/{owner}/{name}"
    repo_key = f"{platform}:{owner.lower()}/{name.lower()}"
    return ParsedRepo(
        platform=platform,  # type: ignore[arg-type]
        owner=owner,
        name=name,
        branch=branch,
        html_url=html_url,
        repo_key=repo_key,
    )
