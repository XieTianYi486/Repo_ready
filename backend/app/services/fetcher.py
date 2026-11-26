from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from ..errors import ScanError
from ..models import Platform
from .http_client import HttpClient
from .platform.base import PlatformAdapter
from .platform.parser import ParsedRepo

RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
MAX_ARCHIVE_ENTRIES = 20000
MAX_SINGLE_FILE_BYTES = 20 * 1024 * 1024
MAX_PATH_CHARS = 240
ROOT_SHA_RE = re.compile(r"-(?P<sha>[0-9a-f]{7,40})$", re.IGNORECASE)


@dataclass
class ExtractResult:
    root: Path
    files_extracted: int
    bytes_extracted: int
    truncated: bool = False
    warnings: list[str] = field(default_factory=list)
    root_name: str | None = None


@dataclass
class GitCloneResult:
    root: Path
    sha: str
    warnings: list[str] = field(default_factory=list)


def download_archive(
    client: HttpClient,
    adapter: PlatformAdapter,
    parsed: ParsedRepo,
    ref: str,
    dest_dir: Path,
    *,
    max_bytes: int,
    by_sha: bool,
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".zip" if parsed.platform == "gitee" else ".tar.gz"
    dest = dest_dir / f"snapshot{suffix}"
    url = adapter.archive_url(parsed, ref, by_sha=by_sha)
    result = client.stream_to_file(
        url,
        dest,
        max_bytes=max_bytes,
        headers={"User-Agent": "RepoReady/1.0"},
        allowed_hosts=adapter.archive_hosts,
    )
    if result.path.stat().st_size > max_bytes:
        raise ScanError(
            "ARCHIVE_TOO_LARGE",
            "仓库归档体积超过限制",
            http_status=413,
        )
    with result.path.open("rb") as handle:
        sample = handle.read(512).lstrip().lower()
    if sample.startswith(b"<!doctype") or sample.startswith(b"<html"):
        raise ScanError(
            "ARCHIVE_BLOCKED",
            "仓库平台返回了 HTML 页面（可能是反爬或登录页），未获取到归档文件",
            http_status=502,
        )
    return result.path


def _sanitize_member(name: str) -> tuple[str | None, str | None]:
    """Return (clean_name, warning).

    clean_name is None for ignorable directory entries. Raises for unsafe names.
    """
    value = (name or "").replace("\\", "/").strip()
    if not value:
        return None, None
    if "\x00" in value:
        raise ScanError("ARCHIVE_UNSAFE", "归档中包含非法文件路径", http_status=400)
    while value.startswith("./"):
        value = value[2:]
    if value.startswith("/"):
        raise ScanError("ARCHIVE_UNSAFE", "归档中包含绝对路径，已拒绝解压", http_status=400)
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        raise ScanError("ARCHIVE_UNSAFE", "归档中包含盘符路径，已拒绝解压", http_status=400)
    raw_parts = value.split("/")
    parts = [part for part in raw_parts if part not in {"", "."}]
    if any(part == ".." for part in parts):
        raise ScanError("ARCHIVE_UNSAFE", "归档中包含路径穿越，已拒绝解压", http_status=400)
    if not parts:
        return None, None
    clean = "/".join(parts)
    if len(clean) > MAX_PATH_CHARS:
        return None, f"跳过过长路径：{clean[:80]}…"
    basename = parts[-1]
    stem = basename.split(".")[0].upper()
    if stem in RESERVED_WINDOWS_NAMES:
        return None, f"跳过 Windows 保留文件名：{clean}"
    if basename.endswith((" ", ".")):
        return None, f"跳过 Windows 不兼容文件名：{clean}"
    return clean, None


def _safe_dest(root: Path, clean_name: str) -> Path:
    target = root.joinpath(*PurePosixPath(clean_name).parts)
    try:
        target.resolve().relative_to(root.resolve())
    except (ValueError, OSError) as exc:
        raise ScanError(
            "ARCHIVE_UNSAFE",
            "归档文件路径越界，已拒绝解压",
            http_status=400,
        ) from exc
    return target


def _write_limited(src, target: Path, remaining_total: int, per_file_limit: int) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with target.open("wb") as handle:
        while True:
            chunk = src.read(64 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > per_file_limit:
                raise ScanError(
                    "ARCHIVE_TOO_LARGE",
                    "归档中存在超大文件，已停止解压",
                    http_status=413,
                )
            if written > remaining_total:
                raise ScanError(
                    "ARCHIVE_TOO_LARGE",
                    "仓库解压后体积超过限制（200MB），已停止解压",
                    http_status=413,
                )
            handle.write(chunk)
    return written


def _finalize_root(dest_dir: Path) -> tuple[Path, str | None]:
    children = list(dest_dir.iterdir())
    if len(children) == 1 and children[0].is_dir() and not children[0].is_symlink():
        return children[0], children[0].name
    return dest_dir, None


def extract_archive(
    archive_path: Path,
    dest_dir: Path,
    *,
    max_extracted_bytes: int,
    max_files: int,
) -> ExtractResult:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with archive_path.open("rb") as handle:
        magic = handle.read(4)
    is_gzip = magic.startswith(b"\x1f\x8b")
    is_zip = magic.startswith(b"PK\x03\x04") or magic.startswith(b"PK\x05\x06")
    if not (is_gzip or is_zip):
        raise ScanError(
            "ARCHIVE_INVALID",
            "无法识别的仓库归档格式",
            http_status=400,
        )

    warnings: list[str] = []
    total_bytes = 0
    extracted_files = 0
    seen_entries = 0
    seen_names: set[str] = set()
    truncated = False

    if is_zip:
        try:
            archive = zipfile.ZipFile(archive_path)
        except zipfile.BadZipFile as exc:
            raise ScanError("ARCHIVE_INVALID", "仓库归档损坏，无法解压", http_status=400) from exc
        with archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                raise ScanError(
                    "TOO_MANY_FILES",
                    "仓库归档条目数量超过限制",
                    http_status=413,
                )
            declared_total = sum(max(0, info.file_size) for info in infos if not info.is_dir())
            if declared_total > max_extracted_bytes:
                raise ScanError(
                    "ARCHIVE_TOO_LARGE",
                    "仓库解压后体积超过限制（200MB）",
                    http_status=413,
                )
            for info in infos:
                seen_entries += 1
                if info.is_dir():
                    continue
                is_symlink = (info.external_attr >> 16) & 0o170000 == 0o120000
                if is_symlink:
                    warnings.append(f"跳过符号链接：{info.filename}")
                    continue
                if info.flag_bits & 0x1:
                    warnings.append(f"跳过加密归档条目：{info.filename}")
                    continue
                clean, warning = _sanitize_member(info.filename)
                if warning:
                    warnings.append(warning)
                if not clean:
                    continue
                if clean.lower() in seen_names:
                    warnings.append(f"跳过大小写冲突条目：{clean}")
                    continue
                seen_names.add(clean.lower())
                if extracted_files >= max_files:
                    truncated = True
                    warnings.append(f"文件数量达到上限（{max_files}），后续文件未解压")
                    break
                if info.file_size > MAX_SINGLE_FILE_BYTES:
                    warnings.append(f"跳过超大文件：{clean}")
                    continue
                target = _safe_dest(dest_dir, clean)
                try:
                    with archive.open(info) as member:
                        written = _write_limited(
                            member,
                            target,
                            max_extracted_bytes - total_bytes,
                            MAX_SINGLE_FILE_BYTES,
                        )
                except ScanError:
                    raise
                except (OSError, RuntimeError) as exc:
                    warnings.append(f"跳过无法解压的文件：{clean}")
                    continue
                total_bytes += written
                extracted_files += 1
    else:
        try:
            tar = tarfile.open(archive_path, mode="r|gz")
        except (tarfile.TarError, OSError) as exc:
            raise ScanError("ARCHIVE_INVALID", "仓库归档损坏，无法解压", http_status=400) from exc
        with tar:
            for member in tar:
                seen_entries += 1
                if seen_entries > MAX_ARCHIVE_ENTRIES:
                    raise ScanError(
                        "TOO_MANY_FILES",
                        "仓库归档条目数量超过限制",
                        http_status=413,
                    )
                if member.isdir():
                    continue
                if not member.isfile():
                    warnings.append(f"跳过非普通文件：{member.name}")
                    continue
                clean, warning = _sanitize_member(member.name)
                if warning:
                    warnings.append(warning)
                if not clean:
                    continue
                if clean.lower() in seen_names:
                    warnings.append(f"跳过大小写冲突条目：{clean}")
                    continue
                seen_names.add(clean.lower())
                if extracted_files >= max_files:
                    truncated = True
                    warnings.append(f"文件数量达到上限（{max_files}），后续文件未解压")
                    break
                if member.size > MAX_SINGLE_FILE_BYTES:
                    warnings.append(f"跳过超大文件：{clean}")
                    continue
                source = tar.extractfile(member)
                if source is None:
                    warnings.append(f"跳过无法读取的文件：{clean}")
                    continue
                target = _safe_dest(dest_dir, clean)
                try:
                    written = _write_limited(
                        source,
                        target,
                        max_extracted_bytes - total_bytes,
                        MAX_SINGLE_FILE_BYTES,
                    )
                except tarfile.TarError:
                    warnings.append(f"跳过无法解压的文件：{clean}")
                    continue
                finally:
                    source.close()
                total_bytes += written
                extracted_files += 1

    if extracted_files == 0:
        raise ScanError(
            "ARCHIVE_EMPTY",
            "仓库归档中没有可读取的文件",
            http_status=422,
        )

    root, root_name = _finalize_root(dest_dir)
    return ExtractResult(
        root=root,
        files_extracted=extracted_files,
        bytes_extracted=total_bytes,
        truncated=truncated,
        warnings=warnings,
        root_name=root_name,
    )


def extract_sha_from_root(root_name: str | None) -> str | None:
    if not root_name:
        return None
    match = ROOT_SHA_RE.search(root_name)
    return match.group("sha") if match else None


def _directory_size(root: Path, limit: int) -> int:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            try:
                total += (Path(dirpath) / filename).stat().st_size
            except OSError:
                continue
            if total > limit:
                return total
    return total


def git_ls_remote_head(parsed: ParsedRepo, branch: str, *, timeout_seconds: int = 20) -> str | None:
    """Best-effort HEAD lookup via git. Used as a Gitee fallback only."""
    if shutil.which("git") is None:
        return None
    url = f"https://{parsed.html_url.split('://', 1)[-1]}.git"
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", url, f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and re.fullmatch(r"[0-9a-f]{40}", parts[0]):
            return parts[0]
    return None


def git_clone_repo(
    parsed: ParsedRepo,
    branch: str,
    dest_dir: Path,
    *,
    max_extracted_bytes: int,
    timeout_seconds: int = 120,
) -> GitCloneResult:
    if shutil.which("git") is None:
        raise ScanError(
            "GIT_UNAVAILABLE",
            "本机未安装 Git，且归档下载失败，无法继续",
            http_status=502,
        )
    dest_dir.mkdir(parents=True, exist_ok=True)
    clone_dir = dest_dir / "clone"
    url = f"https://{parsed.html_url.split('://', 1)[-1]}.git"
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--single-branch",
                "--branch",
                branch,
                "--no-tags",
                url,
                str(clone_dir),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise ScanError(
            "GIT_CLONE_TIMEOUT",
            "Git 克隆超时，且归档下载失败",
            http_status=504,
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        message = detail[-1][:200] if detail else "未知错误"
        raise ScanError(
            "GIT_CLONE_FAILED",
            f"Git 克隆失败：{message}",
            http_status=502,
        )
    size = _directory_size(clone_dir, max_extracted_bytes)
    if size > max_extracted_bytes:
        raise ScanError(
            "ARCHIVE_TOO_LARGE",
            "Git 克隆体积超过限制（200MB）",
            http_status=413,
        )
    sha = ""
    try:
        rev = subprocess.run(
            ["git", "-C", str(clone_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        if rev.returncode == 0:
            sha = rev.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        sha = ""
    git_dir = clone_dir / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir, ignore_errors=True)
    return GitCloneResult(root=clone_dir, sha=sha)
