from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..models import LanguageStat, ProjectInfo
from ..utils.text import decode_text, is_probably_minified, looks_binary

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "bower_components",
    "vendor",
    "dist",
    "build",
    "out",
    "target",
    "bin",
    "obj",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".next",
    ".nuxt",
    ".cache",
    "coverage",
    ".idea",
    ".vscode",
    "Pods",
    "DerivedData",
}

IGNORED_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}

LOCKFILE_NAMES = {
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "go.sum",
    "Cargo.lock",
    "composer.lock",
    "Gemfile.lock",
    "packages.lock.json",
    "pubspec.lock",
}

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".bmp",
    ".tiff",
    ".psd",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".webm",
    ".wav",
    ".flac",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".jar",
    ".war",
    ".ear",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".dat",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".class",
    ".pyc",
    ".pyo",
    ".o",
    ".a",
    ".lib",
    ".lockb",
    ".sqlite",
    ".db",
}

LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".swift": "Swift",
    ".scala": "Scala",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".bat": "Batch",
    ".cmd": "Batch",
    ".vbs": "VBScript",
    ".vue": "Vue",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".less": "Less",
    ".md": "Markdown",
    ".sql": "SQL",
    ".lua": "Lua",
    ".dart": "Dart",
    ".r": "R",
    ".m": "Objective-C",
    ".pl": "Perl",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".clj": "Clojure",
}


@dataclass
class FileEntry:
    rel_path: str
    abs_path: Path
    size: int
    ext: str
    is_binary: bool = False
    scan_text: bool = True
    too_large: bool = False


@dataclass
class FileIndex:
    root: Path
    entries: list[FileEntry]
    files_total: int
    files_skipped: int
    warnings: list[str] = field(default_factory=list)
    truncated: bool = False
    text_bytes_scanned: int = 0
    _by_path: dict[str, FileEntry] = field(default_factory=dict)
    _text_cache: dict[str, str | None] = field(default_factory=dict)
    _max_text_file_bytes: int = 512 * 1024
    _max_total_text_bytes: int = 20 * 1024 * 1024

    def __post_init__(self) -> None:
        if not self._by_path:
            self._by_path = {entry.rel_path: entry for entry in self.entries}

    def get(self, rel_path: str) -> FileEntry | None:
        return self._by_path.get(rel_path)

    def root_files(self) -> list[FileEntry]:
        return [entry for entry in self.entries if "/" not in entry.rel_path]

    def find_root(self, *names: str) -> FileEntry | None:
        wanted = {name.lower() for name in names}
        for entry in self.root_files():
            if entry.rel_path.lower() in wanted:
                return entry
        return None

    def find_root_prefix(self, prefix: str) -> FileEntry | None:
        prefix = prefix.lower()
        for entry in self.root_files():
            if entry.rel_path.lower().startswith(prefix):
                return entry
        return None

    def readme_entry(self) -> FileEntry | None:
        candidates = [
            entry
            for entry in self.root_files()
            if entry.rel_path.lower().startswith("readme")
            and (
                "." not in entry.rel_path
                or entry.ext in {".md", ".markdown", ".rst", ".txt", ".adoc", ""}
            )
        ]
        if not candidates:
            return None

        def priority(entry: FileEntry) -> tuple[int, str]:
            name = entry.rel_path.lower()
            for index, preferred in enumerate(
                ("readme.md", "readme.markdown", "readme.rst", "readme.txt", "readme")
            ):
                if name == preferred:
                    return index, name
            return 50, name

        candidates.sort(key=priority)
        return candidates[0]

    def text_for(self, entry: FileEntry | None) -> str | None:
        if entry is None or entry.is_binary or not entry.scan_text or entry.too_large:
            return None
        key = entry.rel_path
        if key in self._text_cache:
            return self._text_cache[key]
        if entry.size > self._max_text_file_bytes:
            self._text_cache[key] = None
            return None
        if self.text_bytes_scanned + entry.size > self._max_total_text_bytes:
            self._text_cache[key] = None
            return None
        try:
            data = entry.abs_path.read_bytes()
        except OSError:
            self._text_cache[key] = None
            return None
        if looks_binary(data):
            entry.is_binary = True
            self._text_cache[key] = None
            return None
        text = decode_text(data)
        if is_probably_minified(text, entry.rel_path):
            entry.scan_text = False
            self._text_cache[key] = None
            return None
        self.text_bytes_scanned += len(data)
        self._text_cache[key] = text
        return text

    def iter_text_entries(self) -> Iterator[tuple[FileEntry, str]]:
        for entry in self.entries:
            if entry.is_binary or not entry.scan_text:
                continue
            text = self.text_for(entry)
            if text is not None:
                yield entry, text

    def project_info(self) -> ProjectInfo:
        language_counts: dict[str, int] = {}
        paths_lower = [entry.rel_path.lower() for entry in self.entries]
        for entry in self.entries:
            language = LANGUAGE_MAP.get(entry.ext)
            if language:
                language_counts[language] = language_counts.get(language, 0) + 1
        languages = [
            LanguageStat(name=name, files=count)
            for name, count in sorted(
                language_counts.items(), key=lambda item: (-item[1], item[0])
            )[:8]
        ]
        has_ci = any(
            path.startswith(".github/workflows/")
            or path.startswith(".gitee/")
            or path in {".gitlab-ci.yml", ".travis.yml", "jenkinsfile", "azure-pipelines.yml"}
            for path in paths_lower
        )
        has_tests = any(
            "/test/" in f"/{path}/"
            or "/tests/" in f"/{path}/"
            or "/spec/" in f"/{path}/"
            or os.path.basename(path).startswith("test_")
            or ".test." in path
            or ".spec." in path
            for path in paths_lower
        )
        has_license = any(
            "/" not in path and (path.startswith("license") or path.startswith("licence"))
            for path in paths_lower
        )
        has_docker = any(
            "/" not in path and path in {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}
            for path in paths_lower
        ) or any(path.endswith("/dockerfile") for path in paths_lower)
        return ProjectInfo(
            languages=languages,
            has_ci=has_ci,
            has_tests=has_tests,
            has_license=has_license,
            has_docker=has_docker,
            file_count=len(self.entries),
        )


def build_file_index(
    root: Path,
    *,
    max_files: int,
    max_text_file_bytes: int,
    max_total_text_bytes: int,
) -> FileIndex:
    entries: list[FileEntry] = []
    warnings: list[str] = []
    files_total = 0
    files_skipped = 0
    truncated = False

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in IGNORED_DIRS and not name.startswith(".git")
        )
        filenames.sort()
        for filename in filenames:
            if filename in IGNORED_FILES:
                continue
            absolute = Path(dirpath) / filename
            if absolute.is_symlink():
                files_skipped += 1
                continue
            files_total += 1
            if len(entries) >= max_files:
                truncated = True
                continue
            try:
                stat = absolute.stat()
            except OSError:
                files_skipped += 1
                continue
            if not absolute.is_file():
                files_skipped += 1
                continue
            rel = absolute.relative_to(root).as_posix()
            ext = absolute.suffix.lower()
            entry = FileEntry(
                rel_path=rel,
                abs_path=absolute,
                size=stat.st_size,
                ext=ext,
                is_binary=ext in BINARY_EXTENSIONS,
                scan_text=ext not in BINARY_EXTENSIONS
                and not rel.lower().endswith((".min.js", ".min.css", ".map", ".lockb")),
                too_large=stat.st_size > max_text_file_bytes,
            )
            if entry.is_binary or entry.too_large:
                files_skipped += 1
            entries.append(entry)

    if truncated:
        warnings.append(f"文件总数超过上限（{max_files}），仅分析前 {max_files} 个文件")
    index = FileIndex(
        root=root,
        entries=entries,
        files_total=files_total,
        files_skipped=files_skipped,
        warnings=warnings,
        truncated=truncated,
        _max_text_file_bytes=max_text_file_bytes,
        _max_total_text_bytes=max_total_text_bytes,
    )
    # README is the highest-priority text load.
    index.text_for(index.readme_entry())
    return index
