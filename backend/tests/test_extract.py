from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from backend.app.errors import ScanError
from backend.app.services.fetcher import extract_archive


def build_tar(path: Path, entries: list[tuple[str, bytes]], symlink: str | None = None):
    with tarfile.open(path, "w:gz") as archive:
        for name, data in entries:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        if symlink:
            info = tarfile.TarInfo(name=symlink)
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            archive.addfile(info)


def build_zip(path: Path, entries: dict[str, bytes]):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def test_extract_tar_and_strip_root(tmp_path):
    archive_path = tmp_path / "repo.tar.gz"
    build_tar(archive_path, [("demo-main/README.md", b"# Demo\n"), ("demo-main/src/app.py", b"print(1)\n")])
    result = extract_archive(
        archive_path,
        tmp_path / "out",
        max_extracted_bytes=1024 * 1024,
        max_files=100,
    )
    assert result.files_extracted == 2
    assert result.root.name == "demo-main"
    assert (result.root / "README.md").read_text(encoding="utf-8") == "# Demo\n"


def test_extract_zip(tmp_path):
    archive_path = tmp_path / "repo.zip"
    build_zip(archive_path, {"demo-main/README.md": b"# Demo\n"})
    result = extract_archive(
        archive_path,
        tmp_path / "out",
        max_extracted_bytes=1024 * 1024,
        max_files=100,
    )
    assert result.root.name == "demo-main"
    assert (result.root / "README.md").exists()


def test_path_traversal_rejected(tmp_path):
    archive_path = tmp_path / "evil.tar.gz"
    build_tar(archive_path, [("../evil.txt", b"evil")])
    with pytest.raises(ScanError) as exc:
        extract_archive(
            archive_path,
            tmp_path / "out",
            max_extracted_bytes=1024 * 1024,
            max_files=100,
        )
    assert exc.value.code == "ARCHIVE_UNSAFE"


def test_absolute_path_rejected(tmp_path):
    archive_path = tmp_path / "evil.zip"
    build_zip(archive_path, {"/etc/passwd": b"root"})
    with pytest.raises(ScanError) as exc:
        extract_archive(
            archive_path,
            tmp_path / "out",
            max_extracted_bytes=1024 * 1024,
            max_files=100,
        )
    assert exc.value.code == "ARCHIVE_UNSAFE"


def test_symlink_skipped(tmp_path):
    archive_path = tmp_path / "links.tar.gz"
    build_tar(
        archive_path,
        [("demo-main/README.md", b"# Demo\n")],
        symlink="demo-main/link",
    )
    result = extract_archive(
        archive_path,
        tmp_path / "out",
        max_extracted_bytes=1024 * 1024,
        max_files=100,
    )
    assert result.files_extracted == 1
    assert (result.root / "README.md").exists()
    assert not (result.root / "link").exists()
    assert any("符号链接" in warning or "非普通文件" in warning for warning in result.warnings)


def test_zip_bomb_estimated_size_rejected(tmp_path):
    archive_path = tmp_path / "boom.zip"
    build_zip(archive_path, {"demo-main/big.txt": b"x" * 1000})
    with pytest.raises(ScanError) as exc:
        extract_archive(
            archive_path,
            tmp_path / "out",
            max_extracted_bytes=100,
            max_files=100,
        )
    assert exc.value.code == "ARCHIVE_TOO_LARGE"


def test_max_files_truncates(tmp_path):
    archive_path = tmp_path / "many.tar.gz"
    build_tar(
        archive_path,
        [
            ("demo-main/a.txt", b"a"),
            ("demo-main/b.txt", b"b"),
            ("demo-main/c.txt", b"c"),
        ],
    )
    result = extract_archive(
        archive_path,
        tmp_path / "out",
        max_extracted_bytes=1024 * 1024,
        max_files=2,
    )
    assert result.files_extracted == 2
    assert result.truncated is True
    assert any("上限" in warning for warning in result.warnings)


def test_reserved_windows_name_skipped(tmp_path):
    archive_path = tmp_path / "reserved.zip"
    build_zip(archive_path, {"demo-main/CON": b"x", "demo-main/README.md": b"ok"})
    result = extract_archive(
        archive_path,
        tmp_path / "out",
        max_extracted_bytes=1024 * 1024,
        max_files=100,
    )
    assert result.files_extracted == 1
    assert not (result.root / "CON").exists()
    assert any("保留文件名" in warning for warning in result.warnings)


def test_case_collision_skipped(tmp_path):
    archive_path = tmp_path / "case.zip"
    build_zip(archive_path, {"demo-main/A.txt": b"a", "demo-main/a.txt": b"b"})
    result = extract_archive(
        archive_path,
        tmp_path / "out",
        max_extracted_bytes=1024 * 1024,
        max_files=100,
    )
    assert result.files_extracted == 1
    assert any("大小写冲突" in warning for warning in result.warnings)


def test_invalid_archive(tmp_path):
    archive_path = tmp_path / "page.zip"
    archive_path.write_bytes(b"<!DOCTYPE html><html>blocked</html>")
    with pytest.raises(ScanError) as exc:
        extract_archive(
            archive_path,
            tmp_path / "out",
            max_extracted_bytes=1024 * 1024,
            max_files=100,
        )
    assert exc.value.code == "ARCHIVE_INVALID"
