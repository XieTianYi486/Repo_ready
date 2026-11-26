from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import Confidence, Scope, Severity


@dataclass(frozen=True)
class SecretRule:
    id: str
    name: str
    kind: str
    pattern: re.Pattern[str]
    severity: Severity
    docs_severity: Severity | None = None
    group: int = 0
    generic: bool = False
    confidence: Confidence = "high"


SECRET_RULES: tuple[SecretRule, ...] = (
    SecretRule(
        "SEC-ANTHROPIC",
        "Anthropic API Key",
        "anthropic_key",
        re.compile(r"sk-ant-(?:api|admin)\d{0,4}-[A-Za-z0-9_-]{20,}"),
        "critical",
        "high",
    ),
    SecretRule(
        "SEC-OPENAI-PROJ",
        "OpenAI Project Key",
        "openai_key",
        re.compile(r"sk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}"),
        "critical",
        "high",
    ),
    SecretRule(
        "SEC-OPENAI-LEGACY",
        "OpenAI Legacy Key",
        "openai_key",
        re.compile(r"sk-(?!ant-|proj-|svcacct-|admin-)[A-Za-z0-9]{24,}"),
        "high",
        "medium",
    ),
    SecretRule(
        "SEC-AWS",
        "AWS Access Key",
        "aws_access_key",
        re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Z0-9])"),
        "critical",
        "high",
    ),
    SecretRule(
        "SEC-ALIYUN",
        "Aliyun AccessKey",
        "aliyun_access_key",
        re.compile(r"(?<![A-Za-z0-9])LTAI[A-Za-z0-9]{12,24}(?![A-Za-z0-9])"),
        "critical",
        "high",
    ),
    SecretRule(
        "SEC-TENCENT",
        "Tencent Cloud SecretId",
        "tencent_secret_id",
        re.compile(r"(?<![A-Za-z0-9])AKID[A-Za-z0-9]{13,40}(?![A-Za-z0-9])"),
        "critical",
        "high",
    ),
    SecretRule(
        "SEC-GITHUB",
        "GitHub Token",
        "github_token",
        re.compile(r"(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
        "high",
        "medium",
    ),
    SecretRule(
        "SEC-GITLAB",
        "GitLab Token",
        "gitlab_token",
        re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
        "high",
        "medium",
    ),
    SecretRule(
        "SEC-SLACK",
        "Slack Token",
        "slack_token",
        re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
        "high",
        "medium",
    ),
    SecretRule(
        "SEC-GOOGLE",
        "Google API Key",
        "google_api_key",
        re.compile(r"AIza[0-9A-Za-z_-]{35}"),
        "high",
        "medium",
    ),
    SecretRule(
        "SEC-STRIPE",
        "Stripe Live Key",
        "stripe_key",
        re.compile(r"[sr]k_live_[0-9A-Za-z]{20,}"),
        "critical",
        "high",
    ),
    SecretRule(
        "SEC-SENDGRID",
        "SendGrid API Key",
        "sendgrid_key",
        re.compile(r"SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{20,}"),
        "high",
        "medium",
    ),
    SecretRule(
        "SEC-PRIVATE-KEY",
        "Private Key Block",
        "private_key",
        re.compile(
            r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"
        ),
        "critical",
        "high",
    ),
    SecretRule(
        "SEC-JWT",
        "JSON Web Token",
        "jwt",
        re.compile(
            r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
        ),
        "medium",
        "low",
    ),
    SecretRule(
        "SEC-BEARER",
        "Bearer Token",
        "bearer_token",
        re.compile(r"(?i)\bBearer\s+([A-Za-z0-9\-._~+/]{20,}=*)"),
        "high",
        "medium",
        group=1,
    ),
    SecretRule(
        "SEC-AZURE-ACCOUNT-KEY",
        "Azure Storage Account Key",
        "azure_account_key",
        re.compile(r"(?i)AccountKey=([A-Za-z0-9+/=]{20,})"),
        "critical",
        "high",
        group=1,
    ),
    SecretRule(
        "SEC-NPM-AUTH",
        "npm auth token",
        "npm_auth_token",
        re.compile(r"(?i)_authToken\s*=\s*([^\s#]{10,})"),
        "high",
        "medium",
        group=1,
    ),
    SecretRule(
        "SEC-DOCKER-AUTH",
        "Docker registry auth blob",
        "docker_auth",
        re.compile(r'(?i)"auth"\s*:\s*"([A-Za-z0-9+/=]{20,})"'),
        "high",
        "medium",
        group=1,
    ),
    SecretRule(
        "SEC-GENERIC",
        "Generic credential assignment",
        "generic_secret",
        re.compile(
            r"(?i)\b(api[_-]?key|apikey|secret(?:[_-]?(?:access[_-]?)?key)?|access[_-]?key|"
            r"access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|pwd)\b"
            r"\s*[:=]\s*['\"]?([A-Za-z0-9_\-./+=]{12,})['\"]?"
        ),
        "medium",
        "low",
        group=2,
        generic=True,
        confidence="medium",
    ),
)


STRICT_PLACEHOLDER_TOKENS = (
    "example",
    "xxxx",
    "your",
    "dummy",
    "fake",
    "placeholder",
    "changeme",
    "redacted",
    "<",
    ">",
    "${",
    "{{",
    "process.env",
    "os.environ",
    "os.getenv",
    "not-a-real",
)

GENERIC_PLACEHOLDER_TOKENS = STRICT_PLACEHOLDER_TOKENS + (
    "test",
    "sample",
    "demo",
    "secret",
    "token",
    "apikey",
    "password",
    "passwd",
    "null",
    "true",
    "false",
    "none",
    "localhost",
    "127.0.0.1",
    "123456",
    "------",
    "****",
)


def is_obvious_placeholder(value: str, *, specific: bool = True) -> bool:
    raw = (value or "").strip().strip("'\"`")
    if not raw:
        return True
    if raw.startswith("-----BEGIN") and "PRIVATE KEY" in raw:
        return False
    lower = raw.lower()
    tokens = STRICT_PLACEHOLDER_TOKENS if specific else GENERIC_PLACEHOLDER_TOKENS
    if any(token in lower for token in tokens):
        return True
    if len(set(raw)) <= 2:
        return True
    if lower.startswith(("http://", "https://", "file://")):
        return True
    if specific and (len(raw) < 12 or any(ch.isspace() for ch in raw)):
        return True
    if (not specific) and (len(raw) < 12):
        return True
    return False


def severity_for_scope(rule: SecretRule, scope: Scope) -> Severity:
    if scope in {"docs", "test"}:
        return rule.docs_severity or _demote(rule.severity)
    return rule.severity


def _demote(severity: Severity) -> Severity:
    return {
        "critical": "high",
        "high": "medium",
        "medium": "low",
        "low": "info",
        "info": "info",
    }[severity]


def mask_secret(value: str, kind: str = "") -> str:
    value = (value or "").strip()
    if kind == "private_key":
        return "[PRIVATE KEY REDACTED]"
    if kind == "env_file":
        return "[ENV FILE]"
    if not value:
        return "****"
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}…{value[-4:]}"


def _replacement_spans(line: str) -> list[tuple[int, int, str]]:
    replacements: list[tuple[int, int, str]] = []
    for rule in SECRET_RULES:
        for match in rule.pattern.finditer(line):
            try:
                start, end = match.span(rule.group)
                value = match.group(rule.group) or ""
            except (IndexError, AttributeError):
                start, end = match.span()
                value = match.group(0) or ""
            if not value:
                continue
            if is_obvious_placeholder(value, specific=not rule.generic):
                continue
            masked = mask_secret(value, rule.kind)
            if masked == value:
                continue
            replacements.append((start, end, masked))
    if not replacements:
        return []
    # Keep the earliest widest span when overlapping.
    replacements.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    result: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, masked in replacements:
        if start < last_end:
            continue
        result.append((start, end, masked))
        last_end = end
    return result


def mask_secrets_in_line(line: str, limit: int = 240) -> str:
    spans = _replacement_spans(line)
    if spans:
        pieces: list[str] = []
        cursor = 0
        for start, end, masked in spans:
            pieces.append(line[cursor:start])
            pieces.append(masked)
            cursor = end
        pieces.append(line[cursor:])
        line = "".join(pieces)
    line = line.replace("\t", " ").strip()
    if len(line) > limit:
        line = line[: max(0, limit - 1)] + "…"
    return line


def contains_high_confidence_secret(text: str) -> bool:
    for rule in SECRET_RULES:
        if rule.generic:
            continue
        for match in rule.pattern.finditer(text or ""):
            try:
                value = match.group(rule.group) or ""
            except (IndexError, AttributeError):
                value = match.group(0) or ""
            if value and not is_obvious_placeholder(value, specific=True):
                return True
    return False
