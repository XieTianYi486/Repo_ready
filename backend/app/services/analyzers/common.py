from __future__ import annotations

import re
from pathlib import PurePosixPath

from ...models import Confidence, DimensionKey, Risk, Scope, Severity
from ...utils.text import sha1_short, truncate

DOC_EXTENSIONS = {".md", ".markdown", ".rst", ".txt", ".adoc", ".asciidoc"}
SCRIPT_EXTENSIONS = {".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1", ".psm1", ".vbs"}
CONFIG_EXTENSIONS = {
    ".json",
    ".json5",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".properties",
    ".xml",
    ".env",
    ".plist",
}
CONFIG_NAMES = {
    ".npmrc",
    ".pypirc",
    ".editorconfig",
    ".dockerignore",
    "dockerfile",
    "makefile",
    "procfile",
    "pipfile",
    "gemfile",
    "compose.yml",
    "compose.yaml",
    "docker-compose.yml",
    "docker-compose.yaml",
}
SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".java",
    ".kt",
    ".kts",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".hpp",
    ".swift",
    ".scala",
    ".vue",
    ".html",
    ".css",
    ".scss",
    ".less",
    ".sql",
    ".lua",
    ".dart",
    ".r",
    ".m",
    ".pl",
    ".ex",
    ".exs",
    ".clj",
    ".sh",
}

TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|specs?|__tests__|fixtures?|examples?|samples?)(/|$)", re.IGNORECASE
)


def file_scope(path: str) -> Scope:
    lower = path.lower()
    parts = PurePosixPath(lower).parts
    name = parts[-1] if parts else lower
    if lower.startswith(".github/workflows/") or lower.startswith(".gitee/"):
        return "ci"
    if name in {"jenkinsfile", ".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml"}:
        return "ci"
    if TEST_PATH_RE.search(lower) or name.startswith("test_") or ".test." in name or ".spec." in name:
        return "test"
    if lower.startswith("docs/") or lower.startswith("doc/") or name.startswith(
        ("readme", "license", "licence", "changelog", "contributing", "code_of_conduct")
    ):
        return "docs"
    suffix = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if suffix in DOC_EXTENSIONS:
        return "docs"
    if suffix in SCRIPT_EXTENSIONS:
        return "script"
    if name in CONFIG_NAMES or suffix in CONFIG_EXTENSIONS:
        return "config"
    if suffix in SOURCE_EXTENSIONS:
        return "source"
    return "other"


def is_docs_scope(scope: Scope) -> bool:
    return scope in {"docs", "test"}


def demote_severity(severity: Severity) -> Severity:
    return {
        "critical": "high",
        "high": "medium",
        "medium": "low",
        "low": "info",
        "info": "info",
    }[severity]


def mask_user_path(path: str) -> str:
    masked = re.sub(
        r"(?i)([A-Za-z]:\\Users\\)([^\\/]+)", r"\1***", path, count=1
    )
    masked = re.sub(r"(/Users/)([^/]+)", r"\1***", masked, count=1)
    masked = re.sub(r"(/home/)([^/]+)", r"\1***", masked, count=1)
    return masked


def snippet_for_line(text: str, line: int, limit: int = 200) -> str:
    lines = text.splitlines()
    if line < 1 or line > len(lines):
        return ""
    return truncate(lines[line - 1].strip(), limit)


def build_risk(
    *,
    rule_id: str,
    dimension: DimensionKey,
    category: str,
    severity: Severity,
    title: str,
    description: str,
    recommendation: str,
    path: str | None = None,
    line: int | None = None,
    evidence: str | None = None,
    occurrences: int = 1,
    source_url: str | None = None,
    confidence: Confidence = "medium",
    blocking: bool | None = None,
) -> Risk:
    ident = sha1_short(f"{rule_id}|{path or ''}|{line or 0}|{title}", 10)
    if blocking is None:
        blocking = severity == "critical" or (
            severity == "high" and dimension == "security"
        )
    return Risk(
        id=f"R-{rule_id}-{ident}",
        rule_id=rule_id,
        dimension=dimension,
        category=category,
        severity=severity,
        title=title,
        description=description,
        file=path,
        line=line,
        evidence=truncate(evidence, 220) if evidence else None,
        occurrences=max(1, occurrences),
        recommendation=recommendation,
        source_url=source_url,
        confidence=confidence,
        blocking=bool(blocking),
    )


def count_by(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts
