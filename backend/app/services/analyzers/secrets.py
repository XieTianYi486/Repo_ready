from __future__ import annotations

import re
from pathlib import PurePosixPath

from ...models import SecretFinding, SecretsSection
from ...utils.secrets_patterns import (
    SECRET_RULES,
    SecretRule,
    is_obvious_placeholder,
    mask_secrets_in_line,
    mask_secret,
    severity_for_scope,
)
from ...utils.text import line_number_at, line_starts, sha256_short, shannon_entropy
from .common import build_risk, file_scope
from .context import AnalyzerContext, AnalyzerOutput

ENV_FILE_RE = re.compile(r"^\.env(?:$|\.)", re.IGNORECASE)
ENV_EXAMPLE_NAMES = {
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.dist",
}
KEY_FILE_EXTENSIONS = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}
KEY_FILE_NAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
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
ENV_VALUE_PLACEHOLDER_RE = re.compile(
    r"(?i)^(?:$|null|none|true|false|0|1|localhost|127\.0\.0\.1|development|production|test|debug|changeme|example|your[_-]?|xxx|placeholder)"
)


def _is_env_file(name: str) -> bool:
    lower = name.lower()
    if lower in ENV_EXAMPLE_NAMES:
        return False
    if lower.endswith((".example", ".sample", ".template", ".dist")):
        return False
    return bool(ENV_FILE_RE.match(lower))


def _env_has_real_values(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        _key, value = stripped.split("=", 1)
        value = value.strip().strip("'\"")
        if not value:
            continue
        if ENV_VALUE_PLACEHOLDER_RE.match(value):
            continue
        if is_obvious_placeholder(value, specific=False):
            continue
        if len(value) >= 12 and shannon_entropy(value) >= 3.0:
            return True
    return False


def _gitignore_covers_env(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("!"):
            continue
        if ".env" in stripped:
            return True
    return False


def _recommendation(kind: str) -> str:
    if kind == "env_file":
        return (
            "立即从仓库移除 .env，轮换其中所有密钥，将 .env 加入 .gitignore，"
            "并使用 git filter-repo / BFG 清理历史中的敏感值。"
        )
    if kind in {"private_key", "private_key_file"}:
        return "立即吊销/轮换私钥，移除文件，清理 Git 历史，并改用密钥管理服务。"
    if kind == "generic_secret":
        return "确认该值是否为真实凭据；若是，立即轮换并改用环境变量或密钥管理服务，避免提交到仓库。"
    if kind == "bearer_token":
        return "确认 Bearer Token 是否为真实凭据；若是，立即轮换，并避免在源码/文档中硬编码。"
    return "立即轮换该凭据，从仓库与历史记录中移除，并改用环境变量或密钥管理服务。"


DOTTED_IDENTIFIER_RE = re.compile(
    r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)+$"
)
CAMEL_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*$")


def _should_skip_generic(value: str) -> bool:
    if len(value) < 12:
        return True
    if value.startswith(("/", "./", "../")) or "://" in value:
        return True
    entropy = shannon_entropy(value)
    if entropy < 3.3:
        return True
    # Avoid method chains / camelCase identifiers such as
    # configService.selectConfigByKey or user.getPassword.
    if not re.search(r"\d", value) and (
        DOTTED_IDENTIFIER_RE.fullmatch(value) or CAMEL_IDENTIFIER_RE.fullmatch(value)
    ):
        return True
    if not re.search(r"[0-9_\-+=]", value):
        return True
    return False


def _read_gitignore(ctx: AnalyzerContext) -> tuple[bool, str | None]:
    entry = ctx.index.find_root(".gitignore")
    if entry is None:
        return False, None
    text = ctx.index.text_for(entry) or ""
    return _gitignore_covers_env(text), entry.rel_path


def analyze_secrets(ctx: AnalyzerContext) -> AnalyzerOutput:
    findings: list[SecretFinding] = []
    findings_by_key: set[tuple[str, str, int, str]] = set()
    env_files: list[str] = []
    seen_fingerprints: set[str] = set()
    total_findings = 0
    truncated = False

    for entry in ctx.index.entries:
        name = PurePosixPath(entry.rel_path).name
        lower = name.lower()
        if entry.is_binary:
            if (
                entry.ext in KEY_FILE_EXTENSIONS or lower in KEY_FILE_NAMES
            ) and entry.size > 0:
                fingerprint = sha256_short(entry.rel_path, 12)
                findings.append(
                    SecretFinding(
                        rule_id="SEC-KEY-FILE",
                        kind="private_key_file",
                        path=entry.rel_path,
                        line=1,
                        masked="[KEY FILE]",
                        severity="critical",
                        confidence="high",
                        fingerprint=fingerprint,
                    )
                )
            continue
        if lower.endswith((".min.js", ".min.css", ".map")) or lower in LOCKFILE_NAMES:
            continue
        if entry.ext in KEY_FILE_EXTENSIONS or lower in KEY_FILE_NAMES:
            if entry.size > 0:
                text = ctx.index.text_for(entry) or ""
                if "PRIVATE KEY" not in text.upper():
                    fingerprint = sha256_short(entry.rel_path, 12)
                    findings.append(
                        SecretFinding(
                            rule_id="SEC-KEY-FILE",
                            kind="private_key_file",
                            path=entry.rel_path,
                            line=1,
                            masked="[KEY FILE]",
                            severity="critical",
                            confidence="high",
                            fingerprint=fingerprint,
                        )
                    )
                    continue
        is_env_file = _is_env_file(name)
        text = ctx.index.text_for(entry)
        if text is None:
            continue
        if is_env_file:
            env_files.append(entry.rel_path)
            env_text = text
            severity = "critical" if _env_has_real_values(env_text) else "high"
            fingerprint = sha256_short(f"env:{entry.rel_path}", 12)
            findings.append(
                SecretFinding(
                    rule_id="SEC-ENV-FILE",
                    kind="env_file",
                    path=entry.rel_path,
                    line=1,
                    masked="[ENV FILE]",
                    severity=severity,  # type: ignore[arg-type]
                    confidence="high",
                    in_env_file=True,
                    fingerprint=fingerprint,
                )
            )
        starts = line_starts(text)
        scope = file_scope(entry.rel_path)
        per_file = 0
        for rule in SECRET_RULES:
            for match in rule.pattern.finditer(text):
                try:
                    value = match.group(rule.group) or ""
                except (IndexError, AttributeError):
                    value = match.group(0) or ""
                value = value.strip().strip("'\"")
                if not value:
                    continue
                if is_obvious_placeholder(value, specific=not rule.generic):
                    continue
                if rule.generic and _should_skip_generic(value):
                    continue
                severity = severity_for_scope(rule, scope)
                if rule.generic and shannon_entropy(value) >= 3.8 and len(value) >= 24:
                    if severity == "medium":
                        severity = "high"
                line = line_number_at(starts, match.start())
                fingerprint = sha256_short(value, 12)
                key = (rule.id, entry.rel_path, line, fingerprint)
                if key in findings_by_key:
                    continue
                findings_by_key.add(key)
                if fingerprint in seen_fingerprints:
                    continue
                seen_fingerprints.add(fingerprint)
                masked = mask_secret(value, rule.kind)
                findings.append(
                    SecretFinding(
                        rule_id=rule.id,
                        kind=rule.kind,
                        path=entry.rel_path,
                        line=line,
                        masked=masked,
                        severity=severity,
                        confidence=rule.confidence,
                        in_env_file=is_env_file,
                        fingerprint=fingerprint,
                    )
                )
                per_file += 1
                total_findings += 1
                if per_file >= 20:
                    break
                if total_findings >= 100:
                    truncated = True
                    break
            if per_file >= 20 or total_findings >= 100:
                break
        if total_findings >= 100:
            break

    # Deduplicate env-file findings by path and ensure env_files are unique.
    unique_env: list[str] = []
    for path in env_files:
        if path not in unique_env:
            unique_env.append(path)

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1

    critical_count = counts.get("critical", 0)
    high_count = counts.get("high", 0)
    medium_count = counts.get("medium", 0)
    low_count = counts.get("low", 0)
    if critical_count:
        score = 0
    else:
        score = max(
            0,
            100
            - min(70, high_count * 35)
            - min(40, medium_count * 10)
            - min(12, low_count * 3),
        )

    gitignore_covers, gitignore_path = _read_gitignore(ctx)
    env_example = any(
        entry.rel_path.lower() in ENV_EXAMPLE_NAMES
        for entry in ctx.index.root_files()
    )
    risks = []
    high_findings = [
        finding for finding in findings if finding.severity in {"critical", "high"}
    ]
    for finding in high_findings[:30]:
        rule = next((item for item in SECRET_RULES if item.id == finding.rule_id), None)
        title = (
            "提交了 .env 文件"
            if finding.kind == "env_file"
            else (
                "提交了私钥文件"
                if finding.kind == "private_key_file"
                else (f"疑似{rule.name}泄露" if rule else "疑似敏感凭据泄露")
            )
        )
        risks.append(
            build_risk(
                rule_id=finding.rule_id,
                dimension="security",
                category="security",
                severity=finding.severity,
                title=f"{title}：{finding.path}",
                description="仓库中存在可能可直接使用的凭据/密钥，接入或公开前必须处理。",
                recommendation=_recommendation(finding.kind),
                path=finding.path,
                line=finding.line,
                evidence=finding.masked,
                occurrences=1,
                source_url=ctx.source_url(finding.path, finding.line),
                confidence=finding.confidence,
                blocking=True,
            )
        )
    if len(high_findings) > 30:
        risks.append(
            build_risk(
                rule_id="SEC-MANY",
                dimension="security",
                category="security",
                severity="high",
                title=f"发现大量敏感信息（共 {len(high_findings)} 处）",
                description="仓库中多处命中高置信密钥规则，风险面较大。",
                recommendation="按优先级轮换所有凭据，并对仓库历史进行秘密扫描与清理。",
                evidence=", ".join(sorted({finding.kind for finding in high_findings}))[:200],
                occurrences=len(high_findings),
                confidence="high",
                blocking=True,
            )
        )
    medium_groups: dict[tuple[str, str], list[SecretFinding]] = {}
    for finding in findings:
        if finding.severity == "medium" and not finding.in_env_file:
            medium_groups.setdefault((finding.rule_id, finding.path), []).append(finding)
    for (rule_id, path), items in list(medium_groups.items())[:10]:
        rule = next((item for item in SECRET_RULES if item.id == rule_id), None)
        risks.append(
            build_risk(
                rule_id=rule_id,
                dimension="security",
                category="security",
                severity="medium",
                title=f"疑似敏感信息：{path}",
                description="命中泛化凭据或 JWT 规则，需要人工确认真实性。",
                recommendation=_recommendation(rule.kind if rule else "generic_secret"),
                path=path,
                line=items[0].line,
                evidence=items[0].masked,
                occurrences=len(items),
                source_url=ctx.source_url(path, items[0].line),
                confidence="medium",
                blocking=False,
            )
        )
    if low_count:
        first_low = next(
            (finding for finding in findings if finding.severity == "low"), None
        )
        risks.append(
            build_risk(
                rule_id="SEC-LOW-SIGNAL",
                dimension="security",
                category="security",
                severity="low",
                title=f"低置信敏感信息（共 {low_count} 处）",
                description="文档/测试或低置信规则命中的敏感信息，建议人工复核。",
                recommendation="核对是否为真实凭据；如为示例请显式标注为 fake/example。",
                path=first_low.path if first_low else None,
                line=first_low.line if first_low else None,
                evidence=first_low.masked if first_low else None,
                occurrences=low_count,
                source_url=ctx.source_url(
                    first_low.path if first_low else None,
                    first_low.line if first_low else None,
                ),
                confidence="low",
                blocking=False,
            )
        )
    if not gitignore_covers and (unique_env or env_example):
        risks.append(
            build_risk(
                rule_id="SEC-GITIGNORE-ENV",
                dimension="security",
                category="security",
                severity="medium",
                title=".gitignore 未覆盖 .env",
                description="环境变量文件可能被误提交；即使当前未发现真实值，也应提前防护。",
                recommendation="在 .gitignore 添加 .env / .env.*，只保留 .env.example。",
                path=gitignore_path,
                evidence="未找到 .env 忽略规则",
                source_url=ctx.source_url(gitignore_path, 1),
                confidence="high",
                blocking=False,
            )
        )

    reasons = []
    if findings:
        reasons.append(
            f"安全规则命中 {len(findings)} 处：critical {critical_count} / high {high_count} / "
            f"medium {medium_count} / low {low_count}"
        )
        if critical_count:
            reasons.append("存在 critical 凭据：安全维度 0 分，总分封顶")
        elif high_count:
            reasons.append("存在 high 凭据：安全维度大幅扣分，总分封顶")
    else:
        reasons.append("未发现密钥/敏感信息（+100）")
    if unique_env:
        reasons.append(f"发现 {len(unique_env)} 个已提交的 .env 文件")
    if not gitignore_covers and (unique_env or env_example):
        reasons.append(".gitignore 未覆盖 .env")
    if truncated:
        reasons.append("敏感信息证据已截断到 100 条")

    if critical_count:
        summary = "发现 critical 级密钥/私钥泄露，必须先轮换并清理历史。"
    elif high_count:
        summary = "发现高置信敏感信息，接入前必须轮换相关凭据。"
    elif findings:
        summary = "发现少量需要人工复核的敏感信息。"
    else:
        summary = "未发现明显的密钥或敏感信息。"

    section = SecretsSection(
        findings=findings[:100],
        counts_by_severity=counts,
        env_files=unique_env,
        gitignore_env=gitignore_covers,
        score=score,
        summary=summary,
    )
    return AnalyzerOutput(section=section, risks=risks, score=score, reasons=reasons)
