from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from ...models import PathFinding, PathsSection, Severity
from ...utils.text import line_number_at, line_starts, truncate
from .common import (
    build_risk,
    demote_severity,
    file_scope,
    mask_user_path,
)
from .context import AnalyzerContext, AnalyzerOutput

LOCKFILE_NAMES = {
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "poetry.lock",
    "uv.lock",
    "pipfile.lock",
    "go.sum",
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "packages.lock.json",
    "pubspec.lock",
}

PLACEHOLDER_USERS = {
    "user",
    "username",
    "yourname",
    "your_name",
    "your-name",
    "name",
    "example",
    "xxx",
    "someone",
    "youruser",
    "shared",
}
PLACEHOLDER_TOKENS = (
    "<",
    ">",
    "${",
    "{{",
    "%userprofile%",
    "%appdata%",
    "$home",
    "$userprofile",
    "yourname",
    "your_name",
    "username",
    "/path/to",
    "path/to",
    "xxx",
    "example",
    "changeme",
    "todo",
)
REGEX_ESCAPE_RE = re.compile(r"[\\/](?:[dDsSwWbBntr])(?![A-Za-z0-9])")


@dataclass(frozen=True)
class PathRule:
    id: str
    kind: str
    label: str
    pattern: re.Pattern[str]
    severity: Severity
    docs_severity: Severity
    confidence: str
    recommendation: str


RULES: tuple[PathRule, ...] = (
    PathRule(
        "PATH-WIN-DRIVE",
        "windows_drive",
        "Windows 盘符绝对路径",
        re.compile(r"(?<![\w])[A-Za-z]:[\\/](?:[^\s\"'<>|*?\r\n]{2,120})"),
        "high",
        "low",
        "high",
        "把盘符路径改为环境变量、配置项或相对路径；脚本中使用 %USERPROFILE% 等可移植写法。",
    ),
    PathRule(
        "PATH-WIN-UNC",
        "unc",
        "Windows UNC 网络路径",
        re.compile(
            r"(?<![\w])\\\\[A-Za-z0-9_.-]+\\[A-Za-z0-9$_.-]+"
            r"(?:\\[^\s\"'<>|*?\r\n]{1,120})?"
        ),
        "high",
        "low",
        "high",
        "避免在代码/脚本中写死网络共享路径；改为配置项并校验可用性。",
    ),
    PathRule(
        "PATH-MAC-HOME",
        "mac_home",
        "macOS 用户目录路径",
        re.compile(
            r"(?<![\w])/Users/([A-Za-z0-9._-]{1,64})(?:/[^\s\"'`<>]{0,120})?"
        ),
        "high",
        "low",
        "high",
        "使用用户主目录展开（如 Path.home() / ~）或环境变量，避免写死具体用户名。",
    ),
    PathRule(
        "PATH-LINUX-HOME",
        "linux_home",
        "Linux 用户目录路径",
        re.compile(
            r"(?<![\w])/home/([A-Za-z0-9._-]{1,64})(?:/[^\s\"'`<>]{0,120})?"
        ),
        "high",
        "low",
        "high",
        "使用 $HOME / os.path.expanduser() 或配置项，避免写死具体用户目录。",
    ),
    PathRule(
        "PATH-ROOT-MNT",
        "root_mnt",
        "Linux 系统/挂载路径",
        re.compile(
            r"(?<![\w])(?:/root(?:/[^\s\"'`<>]{0,120})?|/mnt/[a-zA-Z](?:/[^\s\"'`<>]{0,120})?)"
        ),
        "medium",
        "low",
        "medium",
        "将系统路径改为可配置项，并在 README 说明挂载与权限要求。",
    ),
    PathRule(
        "PATH-DEPLOY-ABS",
        "deploy_abs",
        "部署绝对路径",
        re.compile(
            r"(?<![\w])(?:/var/www|/opt|/usr/local|/srv)(?:/[^\s\"'`<>]{0,120})"
        ),
        "low",
        "info",
        "medium",
        "通过配置或部署脚本注入路径，避免应用代码依赖固定目录。",
    ),
)


def _inside_url(text: str, start: int) -> bool:
    delimiters = " \t\r\n\"'`(<[{=,;"
    prefix_start = 0
    for index in range(start - 1, max(-1, start - 160), -1):
        if text[index] in delimiters:
            prefix_start = index + 1
            break
    segment = text[prefix_start:start]
    return "://" in segment and "file://" not in segment


def _has_placeholder(value: str) -> bool:
    lower = value.lower()
    compact = value.replace("\\", "/").lower()
    compact = re.sub(r"/+", "/", compact)
    if any(token in lower or token in compact for token in PLACEHOLDER_TOKENS):
        return True
    if REGEX_ESCAPE_RE.search(value):
        return True
    if len(compact) <= 3:
        return True
    return False


def _severity_for_rule(rule: PathRule, scope: str, *, in_comment: bool = False) -> Severity:
    if scope in {"docs", "test", "other"}:
        return rule.docs_severity
    if scope == "ci":
        return demote_severity(rule.severity)
    if in_comment:
        return demote_severity(rule.severity)
    return rule.severity


def _is_comment_prefix(prefix: str) -> bool:
    stripped = prefix.strip()
    if not stripped:
        return False
    if stripped.startswith(("#", "//", "<!--", "*", ";")):
        return True
    if re.match(r"^(?:rem\b|::)", stripped, re.IGNORECASE):
        return True
    return False


def analyze_paths(ctx: AnalyzerContext) -> AnalyzerOutput:
    findings: list[PathFinding] = []
    seen: set[tuple[str, str, int, str]] = set()
    truncated = False
    for entry, text in ctx.index.iter_text_entries():
        name = PurePosixPath(entry.rel_path).name.lower()
        if name in LOCKFILE_NAMES or name.endswith((".min.js", ".min.css", ".map")):
            continue
        scope = file_scope(entry.rel_path)
        starts = line_starts(text)
        file_findings = 0
        for rule in RULES:
            for match in rule.pattern.finditer(text):
                value = match.group(0).strip()
                if not value or _has_placeholder(value):
                    continue
                following = text[match.end() : match.end() + 1]
                if following in "<{%$":
                    continue
                if _inside_url(text, match.start()):
                    continue
                if rule.kind in {"mac_home", "linux_home"}:
                    username = match.group(1) if match.groups() else ""
                    if username.lower() in PLACEHOLDER_USERS:
                        continue
                line = line_number_at(starts, match.start())
                line_start = starts[line - 1] if 0 < line <= len(starts) else 0
                prefix = text[line_start : match.start()]
                in_comment = _is_comment_prefix(prefix) or (
                    "<!--" in prefix and "-->" not in prefix
                )
                masked_value = mask_user_path(value)
                snippet = truncate(masked_value, 180)
                key = (rule.id, entry.rel_path, line, snippet)
                if key in seen:
                    continue
                seen.add(key)
                severity = _severity_for_rule(rule, scope, in_comment=in_comment)
                findings.append(
                    PathFinding(
                        rule_id=rule.id,
                        kind=rule.kind,
                        path=entry.rel_path,
                        line=line,
                        snippet=snippet,
                        severity=severity,
                        scope=scope,  # type: ignore[arg-type]
                        confidence=rule.confidence,  # type: ignore[arg-type]
                    )
                )
                file_findings += 1
                if len(findings) >= 200:
                    truncated = True
                    break
            if len(findings) >= 200:
                break
        if len(findings) >= 200:
            break
        if file_findings >= 30:
            continue

    counts_by_rule: dict[str, int] = {}
    counts_by_severity: dict[str, int] = {}
    for finding in findings:
        counts_by_rule[finding.rule_id] = counts_by_rule.get(finding.rule_id, 0) + 1
        counts_by_severity[finding.severity] = (
            counts_by_severity.get(finding.severity, 0) + 1
        )

    high_groups = {
        (finding.rule_id, finding.path)
        for finding in findings
        if finding.severity == "high"
    }
    medium_groups = {
        (finding.rule_id, finding.path)
        for finding in findings
        if finding.severity == "medium"
    }
    low_groups = {
        (finding.rule_id, finding.path)
        for finding in findings
        if finding.severity == "low"
    }
    penalty = (
        min(60, len(high_groups) * 20)
        + min(24, len(medium_groups) * 8)
        + min(12, len(low_groups) * 3)
    )

    rule_by_id = {rule.id: rule for rule in RULES}
    grouped: dict[tuple[str, str], list[PathFinding]] = {}
    for finding in findings:
        grouped.setdefault((finding.rule_id, finding.path), []).append(finding)

    risks = []
    high_medium_groups = [
        (key, items)
        for key, items in grouped.items()
        if any(item.severity in {"high", "medium"} for item in items)
    ]
    high_medium_groups.sort(
        key=lambda item: (
            min(
                0 if finding.severity == "high" else 1
                for finding in item[1]
                if finding.severity in {"high", "medium"}
            ),
            item[0][0],
            item[0][1],
        )
    )
    for (rule_id, path), items in high_medium_groups[:20]:
        rule = rule_by_id[rule_id]
        severity = min(
            (item.severity for item in items),
            key=lambda value: {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}[value],
        )
        first = items[0]
        risks.append(
            build_risk(
                rule_id=rule_id,
                dimension="cross_platform",
                category="platform",
                severity=severity,
                title=f"{rule.label}：{path}",
                description=f"在 {path} 中发现 {len(items)} 处硬编码绝对路径，换机或换系统后可能直接失效。",
                recommendation=rule.recommendation,
                path=path,
                line=first.line,
                evidence=first.snippet,
                occurrences=len(items),
                source_url=ctx.source_url(path, first.line),
                confidence=first.confidence,
                blocking=False,
            )
        )
    for rule in RULES:
        low_items = [
            finding
            for finding in findings
            if finding.rule_id == rule.id and finding.severity == "low"
        ]
        if not low_items:
            continue
        first = low_items[0]
        risks.append(
            build_risk(
                rule_id=rule.id,
                dimension="cross_platform",
                category="platform",
                severity="low",
                title=f"{rule.label}（低风险，共 {len(low_items)} 处）",
                description="路径主要出现在文档/测试或影响较小，但迁移时仍可能需要调整。",
                recommendation=rule.recommendation,
                path=first.path,
                line=first.line,
                evidence=first.snippet,
                occurrences=len(low_items),
                source_url=ctx.source_url(first.path, first.line),
                confidence=first.confidence,
                blocking=False,
            )
        )

    reasons: list[str] = []
    if findings:
        reasons.append(
            f"发现 {len(findings)} 处硬编码路径（high {counts_by_severity.get('high', 0)} / "
            f"medium {counts_by_severity.get('medium', 0)} / low {counts_by_severity.get('low', 0)}）"
        )
        reasons.append(f"跨平台路径扣分：-{penalty}")
    else:
        reasons.append("未发现硬编码绝对路径（+100）")
    if truncated:
        reasons.append("硬编码路径证据已截断到 200 条")

    summary = (
        f"发现 {len(findings)} 处硬编码路径，涉及 {len(grouped)} 个文件/规则组合。"
        if findings
        else "未发现明显的硬编码绝对路径。"
    )
    section = PathsSection(
        findings=findings[:200],
        counts_by_rule=counts_by_rule,
        counts_by_severity=counts_by_severity,
        penalty=penalty,
        summary=summary,
    )
    return AnalyzerOutput(
        section=section,
        risks=risks,
        score=max(0, 100 - penalty),
        reasons=reasons,
    )
