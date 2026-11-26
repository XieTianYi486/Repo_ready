from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["github", "gitee"]
Severity = Literal["critical", "high", "medium", "low", "info"]
DimensionKey = Literal["readme", "dependencies", "startup", "cross_platform", "security"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]
AiStatus = Literal["disabled", "not_generated", "pending", "ready", "error"]
Scope = Literal["source", "config", "script", "docs", "test", "ci", "other"]
Confidence = Literal["high", "medium", "low"]

SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}
DIMENSION_ORDER: dict[str, int] = {
    "readme": 0,
    "dependencies": 1,
    "startup": 2,
    "cross_platform": 3,
    "security": 4,
}


class AppModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RepoInfo(AppModel):
    platform: Platform
    owner: str
    name: str
    full_name: str
    html_url: str
    default_branch: str
    description: str | None = None
    stars: int = 0
    forks: int = 0
    language: str | None = None
    license: str | None = None
    archived: bool = False
    private: bool = False
    pushed_at: str | None = None
    size_kb: int | None = None


class CommitInfo(AppModel):
    sha: str
    short_sha: str
    branch: str
    message: str = ""
    author: str = ""
    date: str | None = None
    url: str = ""
    source: Literal["api", "archive", "git"] = "api"
    archive_ref: Literal["sha", "branch", "git"] = "sha"
    snapshot_warning: str | None = None


class SectionCheck(AppModel):
    key: str
    label: str
    present: bool


class ReadmeSection(AppModel):
    present: bool = False
    path: str | None = None
    chars: int = 0
    lines: int = 0
    headings: list[str] = Field(default_factory=list)
    code_blocks: int = 0
    images: int = 0
    badges: int = 0
    sections: list[SectionCheck] = Field(default_factory=list)
    has_install: bool = False
    has_usage: bool = False
    has_config: bool = False
    has_api: bool = False
    has_license: bool = False
    placeholders: list[str] = Field(default_factory=list)
    score: int = 0
    summary: str = ""


class ManifestInfo(AppModel):
    path: str
    ecosystem: str
    kind: str
    parse_ok: bool = True
    dependency_count: int = 0
    dev_dependency_count: int = 0
    lockfile: str | None = None
    issues: list[str] = Field(default_factory=list)
    primary: bool = True


class DependenciesSection(AppModel):
    manifests: list[ManifestInfo] = Field(default_factory=list)
    ecosystems: list[str] = Field(default_factory=list)
    lockfiles: list[str] = Field(default_factory=list)
    has_manifest: bool = False
    score: int = 0
    summary: str = ""


class StartupEntry(AppModel):
    source: Literal[
        "package_script",
        "makefile",
        "dockerfile",
        "compose",
        "procfile",
        "pyproject",
        "script",
        "readme",
        "other",
    ]
    path: str | None = None
    command: str
    verified: bool = False
    detail: str = ""


class StartupSection(AppModel):
    entries: list[StartupEntry] = Field(default_factory=list)
    documented_commands: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    env_example: bool = False
    has_docker: bool = False
    has_compose: bool = False
    has_procfile: bool = False
    has_makefile: bool = False
    suggested_command: str | None = None
    mismatches: list[str] = Field(default_factory=list)
    score: int = 0
    summary: str = ""


class WindowsScriptInfo(AppModel):
    path: str
    extension: str
    size: int = 0
    purpose: str = "unknown"
    referenced: bool = False
    flags: list[str] = Field(default_factory=list)
    severity: Severity = "info"


class WindowsSection(AppModel):
    files: list[WindowsScriptInfo] = Field(default_factory=list)
    count: int = 0
    only_windows_start: bool = False
    penalty: int = 0
    summary: str = ""


class PathFinding(AppModel):
    rule_id: str
    kind: str
    path: str
    line: int
    snippet: str
    severity: Severity
    scope: Scope
    confidence: Confidence = "medium"


class PathsSection(AppModel):
    findings: list[PathFinding] = Field(default_factory=list)
    counts_by_rule: dict[str, int] = Field(default_factory=dict)
    counts_by_severity: dict[str, int] = Field(default_factory=dict)
    penalty: int = 0
    summary: str = ""


class SecretFinding(AppModel):
    rule_id: str
    kind: str
    path: str
    line: int
    masked: str
    severity: Severity
    confidence: Confidence = "medium"
    in_env_file: bool = False
    fingerprint: str = ""


class SecretsSection(AppModel):
    findings: list[SecretFinding] = Field(default_factory=list)
    counts_by_severity: dict[str, int] = Field(default_factory=dict)
    env_files: list[str] = Field(default_factory=list)
    gitignore_env: bool = False
    score: int = 0
    summary: str = ""


class ReportSections(AppModel):
    readme: ReadmeSection = Field(default_factory=ReadmeSection)
    dependencies: DependenciesSection = Field(default_factory=DependenciesSection)
    startup: StartupSection = Field(default_factory=StartupSection)
    windows: WindowsSection = Field(default_factory=WindowsSection)
    paths: PathsSection = Field(default_factory=PathsSection)
    secrets: SecretsSection = Field(default_factory=SecretsSection)


class Risk(AppModel):
    id: str
    rule_id: str
    dimension: DimensionKey
    category: str
    severity: Severity
    title: str
    description: str
    file: str | None = None
    line: int | None = None
    evidence: str | None = None
    occurrences: int = 1
    recommendation: str = ""
    source_url: str | None = None
    confidence: Confidence = "medium"
    blocking: bool = False


class DimensionScore(AppModel):
    key: DimensionKey
    name: str
    score: int
    weight: int
    weighted: float
    status: str
    summary: str
    reasons: list[str] = Field(default_factory=list)
    risk_ids: list[str] = Field(default_factory=list)


class ScoreInfo(AppModel):
    total: int
    raw_total: int
    grade: Literal["A", "B", "C", "D", "F"]
    label: str
    capped: bool = False
    cap_reason: list[str] = Field(default_factory=list)
    dimensions: list[DimensionScore] = Field(default_factory=list)
    formula_version: str
    fingerprint: str


class AiBlocker(AppModel):
    title: str
    why: str
    fix: str
    severity: Severity = "high"


class AiQuickWin(AppModel):
    action: str
    effect: str


class AiStep(AppModel):
    step: int
    detail: str


class AiAdvice(AppModel):
    status: AiStatus = "disabled"
    provider: str | None = None
    model: str | None = None
    generated_at: str | None = None
    latency_ms: int | None = None
    summary: str = ""
    reference_score: int | None = None
    score_reason: str = ""
    blockers: list[AiBlocker] = Field(default_factory=list)
    quick_wins: list[AiQuickWin] = Field(default_factory=list)
    integration_plan: list[AiStep] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    error: str | None = None


class UpdateInfo(AppModel):
    previous_commit: str | None = None
    previous_report_id: str | None = None
    has_previous: bool = False
    note: str | None = None


class SnapshotInfo(AppModel):
    compressed_bytes: int = 0
    extracted_bytes: int = 0
    files_total: int = 0
    files_scanned: int = 0
    files_skipped: int = 0
    text_bytes_scanned: int = 0
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class LanguageStat(AppModel):
    name: str
    files: int


class ProjectInfo(AppModel):
    languages: list[LanguageStat] = Field(default_factory=list)
    has_ci: bool = False
    has_tests: bool = False
    has_license: bool = False
    has_docker: bool = False
    file_count: int = 0


class Report(AppModel):
    id: str
    schema_version: str
    tool_version: str
    rules_version: str
    platform: Platform
    repo: RepoInfo
    commit: CommitInfo
    analyzed_at: str
    duration_ms: int
    cached: bool = False
    score: ScoreInfo
    sections: ReportSections = Field(default_factory=ReportSections)
    risks: list[Risk] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    ai: AiAdvice = Field(default_factory=AiAdvice)
    update: UpdateInfo = Field(default_factory=UpdateInfo)
    limits: SnapshotInfo = Field(default_factory=SnapshotInfo)
    project: ProjectInfo = Field(default_factory=ProjectInfo)


class ScanRequest(AppModel):
    url: str
    branch: str | None = None
    force: bool = False


class ScanStartResponse(AppModel):
    job_id: str
    status: JobStatus


class ScanJobPublic(AppModel):
    job_id: str
    status: JobStatus
    stage: str
    stage_label: str
    message: str = ""
    progress: int
    url: str
    report_id: str | None = None
    cached: bool = False
    error_code: str | None = None
    error_message: str | None = None
    elapsed_ms: int = 0
    created_at: str
    updated_at: str


class ReportSummary(AppModel):
    id: str
    platform: Platform
    full_name: str
    branch: str
    commit_short_sha: str
    total: int
    grade: str
    analyzed_at: str
    cached: bool = False


class AiHealth(AppModel):
    enabled: bool
    provider: str | None = None
    model: str | None = None


class TokenHealth(AppModel):
    github: bool = False
    gitee: bool = False


class HealthResponse(AppModel):
    status: str = "ok"
    version: str
    rules_version: str
    ai: AiHealth
    tokens: TokenHealth


class UpdateCheckResponse(AppModel):
    status: Literal["up_to_date", "update_available", "unknown"]
    current_commit: str
    latest_commit: str | None = None
    latest_short: str | None = None
    message: str = ""
    retry_after: int | None = None


class ErrorResponse(AppModel):
    error_code: str
    message: str
    details: str | None = None
    retry_after: int | None = None
