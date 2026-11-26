from __future__ import annotations

import httpx
import pytest

from backend.app.errors import ScanError
from backend.app.services.http_client import JsonResult
from backend.app.services.platform.gitee import GiteeAdapter
from backend.app.services.platform.github import GitHubAdapter
from backend.app.services.platform.parser import parse_repo_url


class FakeClient:
    def __init__(self, *results: JsonResult):
        self.results = list(results)
        self.calls: list[tuple[str, dict]] = []

    def get_json(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.results.pop(0)


def result(status: int, data, headers: dict | None = None) -> JsonResult:
    return JsonResult(status=status, data=data, headers=httpx.Headers(headers or {}), url="https://api")


def test_github_meta_and_headers():
    parsed = parse_repo_url("https://github.com/o/r")
    client = FakeClient(
        result(
            200,
            {
                "private": False,
                "full_name": "o/r",
                "html_url": "https://github.com/o/r",
                "default_branch": "main",
                "description": "demo",
                "stargazers_count": 10,
                "forks_count": 2,
                "language": "Python",
                "license": {"spdx_id": "MIT"},
                "archived": False,
                "pushed_at": "2026-01-01T00:00:00Z",
                "size": 12,
            },
        )
    )
    repo = GitHubAdapter(token="secret-token").fetch_meta(client, parsed)
    assert repo.full_name == "o/r"
    assert repo.license == "MIT"
    assert repo.stars == 10
    url, kwargs = client.calls[0]
    assert url.endswith("/repos/o/r")
    assert kwargs["headers"]["Authorization"] == "Bearer secret-token"
    assert kwargs["headers"]["X-GitHub-Api-Version"] == "2022-11-28"


def test_github_private_repo_rejected():
    parsed = parse_repo_url("https://github.com/o/r")
    client = FakeClient(result(200, {"private": True}))
    with pytest.raises(ScanError) as exc:
        GitHubAdapter().fetch_meta(client, parsed)
    assert exc.value.code == "PRIVATE_REPO"


def test_github_rate_limit_and_not_found():
    parsed = parse_repo_url("https://github.com/o/r")
    with pytest.raises(ScanError) as exc:
        GitHubAdapter().fetch_meta(
            FakeClient(result(403, {}, {"x-ratelimit-remaining": "0"})), parsed
        )
    assert exc.value.code == "RATE_LIMITED"
    with pytest.raises(ScanError) as exc:
        GitHubAdapter().fetch_meta(FakeClient(result(404, {})), parsed)
    assert exc.value.code == "REPO_NOT_FOUND"


def test_github_head():
    parsed = parse_repo_url("https://github.com/o/r")
    client = FakeClient(
        result(
            200,
            {
                "name": "main",
                "commit": {
                    "sha": "a" * 40,
                    "commit": {
                        "message": "first line\nsecond line",
                        "author": {"name": "Alice", "date": "2026-01-01T00:00:00Z"},
                    },
                },
            },
        )
    )
    commit = GitHubAdapter().fetch_head(client, parsed, "main")
    assert commit.sha == "a" * 40
    assert commit.message == "first line"
    assert commit.author == "Alice"
    assert commit.short_sha == "a" * 7


def test_github_branch_not_found():
    parsed = parse_repo_url("https://github.com/o/r")
    with pytest.raises(ScanError) as exc:
        GitHubAdapter().fetch_head(FakeClient(result(404, {})), parsed, "missing")
    assert exc.value.code == "BRANCH_NOT_FOUND"


def test_gitee_meta_and_token():
    parsed = parse_repo_url("https://gitee.com/o/r")
    client = FakeClient(
        result(
            200,
            {
                "private": False,
                "full_name": "o/r",
                "default_branch": "master",
                "stargazers_count": 1,
                "forks_count": 2,
                "language": "Java",
                "license": "MIT",
                "pushed_at": "2026-01-01T00:00:00+08:00",
            },
        )
    )
    repo = GiteeAdapter(token="gitee-token").fetch_meta(client, parsed)
    assert repo.default_branch == "master"
    assert repo.license == "MIT"
    _, kwargs = client.calls[0]
    assert kwargs["params"] == {"access_token": "gitee-token"}
    assert not kwargs["headers"].get("Authorization")


def test_gitee_head():
    parsed = parse_repo_url("https://gitee.com/o/r")
    client = FakeClient(
        result(
            200,
            {
                "name": "master",
                "commit": {
                    "sha": "b" * 40,
                    "commit": {
                        "message": "feat: demo",
                        "author": {"name": "Bob", "date": "2026-01-01T00:00:00+08:00"},
                    },
                },
            },
        )
    )
    commit = GiteeAdapter().fetch_head(client, parsed, "master")
    assert commit.sha == "b" * 40
    assert commit.message == "feat: demo"
    assert commit.author == "Bob"


def test_archive_and_blob_urls():
    github = parse_repo_url("https://github.com/o/r")
    gitee = parse_repo_url("https://gitee.com/o/r")
    sha = "a" * 40
    assert GitHubAdapter().archive_url(github, sha, by_sha=True) == (
        f"https://codeload.github.com/o/r/tar.gz/{sha}"
    )
    assert GiteeAdapter().archive_url(gitee, sha, by_sha=True) == (
        f"https://gitee.com/o/r/repository/archive/{sha}.zip"
    )
    assert GitHubAdapter().blob_url(github, sha, "src/app.py", 12) == (
        f"https://github.com/o/r/blob/{sha}/src/app.py#L12"
    )
    assert GiteeAdapter().blob_url(gitee, sha, "src/app.py") == (
        f"https://gitee.com/o/r/blob/{sha}/src/app.py"
    )
    assert GitHubAdapter().blob_url(github, sha, "a b/c.py", 1).endswith(
        "/blob/" + sha + "/a%20b/c.py#L1"
    )


def test_remote_head_urls():
    parsed = parse_repo_url("https://github.com/o/r")
    adapter = GitHubAdapter()
    assert adapter.tree_url(parsed, "x" * 40).endswith("/tree/" + "x" * 40)
    assert adapter.commit_url(parsed, "x" * 40).endswith("/commit/" + "x" * 40)
