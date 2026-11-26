from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.errors import ScanError
from backend.app.services.fetcher import download_archive
from backend.app.services.http_client import DownloadResult
from backend.app.services.platform.github import GitHubAdapter
from backend.app.services.platform.parser import parse_repo_url


class FakeDownloadClient:
    def __init__(self, payload: bytes):
        self.payload = payload

    def stream_to_file(self, url, dest: Path, *, max_bytes, headers, allowed_hosts):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.payload)
        return DownloadResult(path=dest, bytes_written=len(self.payload), final_url=url)


def test_html_archive_is_rejected(tmp_path):
    parsed = parse_repo_url("https://github.com/o/r")
    client = FakeDownloadClient(b"<!DOCTYPE html><html>blocked</html>")
    with pytest.raises(ScanError) as exc:
        download_archive(
            client,  # type: ignore[arg-type]
            GitHubAdapter(),
            parsed,
            "a" * 40,
            tmp_path / "dl",
            max_bytes=1024,
            by_sha=True,
        )
    assert exc.value.code == "ARCHIVE_BLOCKED"


def test_valid_archive_returned(tmp_path):
    parsed = parse_repo_url("https://github.com/o/r")
    payload = b"\x1f\x8b\x08\x00" + b"x" * 100
    client = FakeDownloadClient(payload)
    path = download_archive(
        client,  # type: ignore[arg-type]
        GitHubAdapter(),
        parsed,
        "a" * 40,
        tmp_path / "dl",
        max_bytes=1024,
        by_sha=True,
    )
    assert path.exists()
    assert path.read_bytes().startswith(b"\x1f\x8b")


def test_oversize_archive_rejected(tmp_path):
    parsed = parse_repo_url("https://github.com/o/r")
    client = FakeDownloadClient(b"x" * 50)
    with pytest.raises(ScanError) as exc:
        download_archive(
            client,  # type: ignore[arg-type]
            GitHubAdapter(),
            parsed,
            "a" * 40,
            tmp_path / "dl",
            max_bytes=10,
            by_sha=True,
        )
    assert exc.value.code == "ARCHIVE_TOO_LARGE"
