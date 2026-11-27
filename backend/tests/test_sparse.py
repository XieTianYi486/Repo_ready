from __future__ import annotations

from pathlib import Path

from backend.app.services.http_client import DownloadResult
from backend.app.services.platform.base import TreeEntry, TreeResult
from backend.app.services.sparse import build_sparse_snapshot


class FakeAdapter:
    raw_hosts = ("raw.example.com",)

    def fetch_tree(self, client, parsed, sha):
        return TreeResult(
            entries=[
                TreeEntry("README.md", size=20),
                TreeEntry("package.json", size=30),
                TreeEntry("package-lock.json", size=40000),
                TreeEntry("scripts/start.ps1", size=20),
                TreeEntry("src/app.py", size=20),
                TreeEntry("assets/logo.png", size=20),
                TreeEntry("big.txt", size=2_000_000),
                TreeEntry("deep/very/deep/file.py", size=10),
            ],
            truncated=True,
        )

    def raw_url(self, parsed, sha, path):
        return f"https://raw.example.com/{path}"


class FakeClient:
    contents = {
        "README.md": b"# Redis-like demo\n",
        "package.json": b'{"scripts":{"start":"node app.js"}}',
        "scripts/start.ps1": b"Write-Host start\n",
        "src/app.py": b"print('hi')\n",
        "assets/logo.png": b"\x89PNG\r\n\x1a\n",
        "deep/very/deep/file.py": b"x=1\n",
    }

    def stream_to_file(self, url, dest: Path, *, max_bytes, headers, allowed_hosts):
        name = url.split("raw.example.com/", 1)[-1]
        data = self.contents.get(name)
        if data is None:
            raise RuntimeError("missing fixture")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return DownloadResult(path=dest, bytes_written=len(data), final_url=url)


def test_sparse_snapshot_selects_key_files_and_marks_partial(tmp_path):
    result = build_sparse_snapshot(
        FakeClient(),  # type: ignore[arg-type]
        FakeAdapter(),  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        "a" * 40,
        tmp_path / "sparse",
    )
    assert result.truncated is True
    assert result.tree_truncated is True
    assert (result.root / "README.md").read_text(encoding="utf-8").startswith("# Redis")
    assert (result.root / "package.json").exists()
    assert (result.root / "scripts/start.ps1").exists()
    assert (result.root / "src/app.py").exists()
    assert (result.root / "package-lock.json").exists()
    assert (result.root / "package-lock.json").stat().st_size == 0
    assert not (result.root / "big.txt").exists()
    assert not (result.root / "assets/logo.png").exists()
    assert any("稀疏快照" in warning for warning in result.warnings)
    assert result.files_written >= 5
