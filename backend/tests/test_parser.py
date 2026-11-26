from __future__ import annotations

import pytest

from backend.app.errors import ScanError
from backend.app.services.platform.parser import parse_repo_url


@pytest.mark.parametrize(
    "raw,platform,owner,name,branch",
    [
        ("https://github.com/octocat/Hello-World", "github", "octocat", "Hello-World", None),
        ("https://github.com/octocat/Hello-World.git", "github", "octocat", "Hello-World", None),
        ("https://github.com/octocat/Hello-World/", "github", "octocat", "Hello-World", None),
        ("https://www.github.com/octocat/Hello-World", "github", "octocat", "Hello-World", None),
        ("github.com/octocat/Hello-World", "github", "octocat", "Hello-World", None),
        ("http://github.com/octocat/Hello-World", "github", "octocat", "Hello-World", None),
        ("https://github.com/octocat/Hello-World/tree/dev", "github", "octocat", "Hello-World", "dev"),
        ("git@github.com:octocat/Hello-World.git", "github", "octocat", "Hello-World", None),
        ("https://gitee.com/y_project/RuoYi", "gitee", "y_project", "RuoYi", None),
        ("https://gitee.com/y_project/RuoYi.git", "gitee", "y_project", "RuoYi", None),
        ("git@gitee.com:y_project/RuoYi.git", "gitee", "y_project", "RuoYi", None),
        ("https://gitee.com/y_project/RuoYi/tree/master", "gitee", "y_project", "RuoYi", "master"),
        ("https://github.com/a/b.c_d-e", "github", "a", "b.c_d-e", None),
    ],
)
def test_valid_urls(raw, platform, owner, name, branch):
    parsed = parse_repo_url(raw)
    assert parsed.platform == platform
    assert parsed.owner == owner
    assert parsed.name == name
    assert parsed.branch == branch
    assert parsed.html_url.startswith("https://")


def test_branch_override():
    parsed = parse_repo_url("https://github.com/a/b", branch_override="release/1.0")
    assert parsed.branch == "release/1.0"


@pytest.mark.parametrize(
    "raw,code",
    [
        ("", "INVALID_URL"),
        ("   ", "INVALID_URL"),
        ("ftp://github.com/a/b", "INVALID_URL"),
        ("javascript:alert(1)", "INVALID_URL"),
        ("https://github.com/a", "INVALID_URL"),
        ("https://gitlab.com/a/b", "UNSUPPORTED_PLATFORM"),
        ("https://github.com.evil.com/a/b", "UNSUPPORTED_PLATFORM"),
        ("https://github.com@evil.com/a/b", "INVALID_URL"),
        ("http://127.0.0.1/a/b", "UNSUPPORTED_PLATFORM"),
        ("https://github.com:8080/a/b", "INVALID_URL"),
        ("https://user:pass@github.com/a/b", "INVALID_URL"),
        ("https://github.com/a/..", "INVALID_URL"),
        ("https://github.com/a/%2e%2e", "INVALID_URL"),
        ("https://github.com/a/b/tree/../evil", "INVALID_URL"),
    ],
)
def test_invalid_urls(raw, code):
    with pytest.raises(ScanError) as exc:
        parse_repo_url(raw)
    assert exc.value.code == code


def test_query_and_fragment_are_ignored():
    parsed = parse_repo_url("https://github.com/a/b?tab=readme#top")
    assert parsed.full_name == "a/b"
    assert parsed.branch is None


def test_repo_key_and_full_name():
    parsed = parse_repo_url("https://GitHub.com/Owner/Repo")
    assert parsed.repo_key == "github:owner/repo"
    assert parsed.full_name == "Owner/Repo"


def test_branch_override_rejects_traversal():
    with pytest.raises(ScanError):
        parse_repo_url("https://github.com/a/b", branch_override="../main")
