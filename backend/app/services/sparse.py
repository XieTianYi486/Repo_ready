from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from ..errors import ScanError
from .file_index import BINARY_EXTENSIONS, IGNORED_DIRS, LOCKFILE_NAMES
from .http_client import HttpClient
from .platform.base import PlatformAdapter, TreeEntry
from .platform.parser import ParsedRepo

MAX_SPARSE_FILES = 420
MAX_SPARSE_BYTES = 20 * 1024 * 1024
MAX_SPARSE_FILE_BYTES = 512 * 1024
MAX_ROOT_FILES = 220
MAX_MANIFESTS = 80
MAX_WINDOWS = 100
MAX_ENV_FILES = 40
MAX_CONFIGS = 100
MAX_SOURCES = 160

MANIFEST_NAMES = {
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "composer.json",
    "composer.lock",
    "pyproject.toml",
    "pipfile",
    "pipfile.lock",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "poetry.lock",
    "uv.lock",
    "go.mod",
    "go.sum",
    "cargo.toml",
    "cargo.lock",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "gemfile",
    "gemfile.lock",
    "pubspec.yaml",
    "pubspec.lock",
    "package.swift",
    "environment.yml",
    "environment.yaml",
}

CONFIG_EXTENSIONS = {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".properties",
    ".xml",
    ".env",
}
SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".swift",
    ".scala",
    ".vue",
    ".sh",
    ".bat",
    ".cmd",
    ".ps1",
    ".vbs",
}
WINDOWS_EXTENSIONS = {".bat", ".cmd", ".ps1", ".vbs"}


@dataclass
class SparseResult:
    root: Path
    files_written: int
    bytes_written: int
    truncated: bool = True
    tree_truncated: bool = False
    warnings: list[str] = field(default_factory=list)


def _is_ignored_path(path: str) -> bool:
    parts = [part.lower() for part in PurePosixPath(path).parts]
    return any(part in IGNORED_DIRS for part in parts)


def _safe_path(dest_dir: Path, path: str) -> Path | None:
    try:
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts:
            return None
        target = dest_dir.joinpath(*pure.parts)
        target.resolve().relative_to(dest_dir.resolve())
        return target
    except (ValueError, OSError):
        return None


def _is_manifest(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    if name in MANIFEST_NAMES:
        return True
    if name.startswith("requirements") and name.endswith(".txt"):
        return True
    return name.endswith(".csproj") or name.endswith(".sln")


def _is_env_file(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    return name == ".env" or (name.startswith(".env.") and not name.endswith(".example"))


def _select(entries: list[TreeEntry]) -> tuple[dict[str, tuple[TreeEntry, bool]], list[str]]:
    selected: dict[str, tuple[TreeEntry, bool]] = {}
    warnings: list[str] = []
    root: list[TreeEntry] = []
    manifests: list[TreeEntry] = []
    lockfiles: list[TreeEntry] = []
    windows: list[TreeEntry] = []
    envs: list[TreeEntry] = []
    configs: list[TreeEntry] = []
    sources: list[TreeEntry] = []

    for entry in entries:
        path = entry.path.replace("\\", "/").strip()
        if not path or _is_ignored_path(path):
            continue
        pure = PurePosixPath(path)
        name = pure.name.lower()
        suffix = pure.suffix.lower()
        if entry.size and entry.size > MAX_SPARSE_FILE_BYTES and name not in LOCKFILE_NAMES:
            continue
        if suffix in BINARY_EXTENSIONS:
            if name in LOCKFILE_NAMES:
                lockfiles.append(entry)
            continue
        if name in LOCKFILE_NAMES:
            lockfiles.append(entry)
            continue
        if _is_manifest(path):
            manifests.append(entry)
            continue
        if suffix in WINDOWS_EXTENSIONS:
            windows.append(entry)
            continue
        if _is_env_file(path):
            envs.append(entry)
            continue
        depth = len(pure.parts) - 1
        if suffix in CONFIG_EXTENSIONS:
            configs.append(entry)
            continue
        if depth <= 3 and suffix in SOURCE_EXTENSIONS:
            sources.append(entry)
            continue
        if depth == 0:
            root.append(entry)

    def add(entries_to_add: list[TreeEntry], limit: int, *, placeholder: bool = False) -> None:
        count = 0
        for entry in entries_to_add:
            if len(selected) >= MAX_SPARSE_FILES or count >= limit:
                break
            path = entry.path.replace("\\", "/").strip()
            if path in selected:
                continue
            if not placeholder and entry.size > MAX_SPARSE_FILE_BYTES:
                warnings.append(f"跳过超大文件：{path}")
                continue
            selected[path] = (entry, placeholder)
            count += 1

    add(root, MAX_ROOT_FILES)
    add(manifests, MAX_MANIFESTS)
    add(lockfiles, len(lockfiles), placeholder=True)
    add(windows, MAX_WINDOWS)
    add(envs, MAX_ENV_FILES)
    add(configs, MAX_CONFIGS)
    add(sources, MAX_SOURCES)

    if len(selected) >= MAX_SPARSE_FILES:
        warnings.append(f"稀疏快照文件数达到上限（{MAX_SPARSE_FILES}），部分文件未纳入")
    return selected, warnings


def build_sparse_snapshot(
    client: HttpClient,
    adapter: PlatformAdapter,
    parsed: ParsedRepo,
    sha: str,
    dest_dir: Path,
    *,
    max_files: int = MAX_SPARSE_FILES,
    max_bytes: int = MAX_SPARSE_BYTES,
) -> SparseResult:
    """Build a best-effort local snapshot from tree + raw files.

    Used when a repository archive is too large to fetch/extract. The report
    must be marked as truncated; this is not a complete scan.
    """
    tree = adapter.fetch_tree(client, parsed, sha)
    if not tree.entries:
        raise ScanError(
            "TREE_EMPTY",
            "无法获取仓库文件树，超大仓库稀疏扫描失败",
            http_status=502,
        )
    selected, selection_warnings = _select(tree.entries)
    # Keep the fetch budget reasonably bounded. Unknown sizes are estimated.
    estimated = 0
    for path, (entry, placeholder) in selected.items():
        if placeholder:
            continue
        estimated += entry.size or 256 * 1024
    if estimated > max_bytes:
        # Trim source/config tail first; root/manifests/scripts are already first.
        kept: dict[str, tuple[TreeEntry, bool]] = {}
        used = 0
        for path, item in selected.items():
            entry, placeholder = item
            cost = 0 if placeholder else (entry.size or 256 * 1024)
            if not placeholder and used + cost > max_bytes:
                selection_warnings.append(f"稀疏快照体积达到上限，跳过：{path}")
                continue
            if len(kept) >= max_files:
                break
            kept[path] = item
            used += cost
        selected = kept

    dest_dir.mkdir(parents=True, exist_ok=True)
    warnings = list(selection_warnings)
    if tree.truncated:
        warnings.append("仓库文件树被平台截断，稀疏快照仅覆盖可见文件")
    files_written = 0
    bytes_written = 0
    budget_lock = threading.Lock()

    def write_placeholder(path: str) -> None:
        target = _safe_path(dest_dir, path)
        if target is None:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"")

    for path, (_entry, placeholder) in selected.items():
        if placeholder:
            write_placeholder(path)
            files_written += 1

    def fetch_one(path: str, entry: TreeEntry) -> tuple[str, int, str | None]:
        target = _safe_path(dest_dir, path)
        if target is None:
            return path, 0, "跳过非法路径"
        try:
            result = client.stream_to_file(
                adapter.raw_url(parsed, sha, path),
                target,
                max_bytes=min(MAX_SPARSE_FILE_BYTES, max_bytes),
                headers={"User-Agent": "RepoReady/1.0"},
                allowed_hosts=adapter.raw_hosts,
            )
            sample = target.read_bytes()[:64].lstrip().lower()
            if sample.startswith(b"<!doctype") or sample.startswith(b"<html"):
                target.unlink(missing_ok=True)
                return path, 0, "平台返回 HTML 页面，已跳过"
            return path, result.bytes_written, None
        except ScanError as exc:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            return path, 0, exc.message
        except OSError:
            return path, 0, "写入稀疏文件失败"

    content_items = [
        (path, entry)
        for path, (entry, placeholder) in selected.items()
        if not placeholder
    ]
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="repoready-sparse") as pool:
        futures = [pool.submit(fetch_one, path, entry) for path, entry in content_items]
        for future in as_completed(futures):
            try:
                path, written, warning = future.result()
            except Exception:
                warnings.append("稀疏文件获取异常")
                continue
            if warning:
                warnings.append(f"{path}：{warning}")
                continue
            with budget_lock:
                files_written += 1
                bytes_written += written

    if files_written == 0:
        raise ScanError(
            "SPARSE_EMPTY",
            "超大仓库稀疏扫描未获取到可用文件，请稍后重试",
            http_status=502,
        )
    if bytes_written > max_bytes:
        warnings.append("稀疏快照实际体积超过预算，已按单文件上限截断")
    warnings.append(
        "超大仓库：已使用稀疏快照，仅分析 README、清单、启动/Windows 脚本与配置/源码样本；"
        "路径与密钥结果可能不完整"
    )
    return SparseResult(
        root=dest_dir,
        files_written=files_written,
        bytes_written=bytes_written,
        tree_truncated=tree.truncated,
        warnings=warnings[:30],
    )
