export type Platform = "github" | "gitee";
export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type DimensionKey =
  | "readme"
  | "dependencies"
  | "startup"
  | "cross_platform"
  | "security";
export type JobStatus = "queued" | "running" | "succeeded" | "failed";
export type AiStatus = "disabled" | "not_generated" | "pending" | "ready" | "error";

export interface Health {
  status: string;
  version: string;
  rules_version: string;
  ai: {
    enabled: boolean;
    provider: string | null;
    model: string | null;
    auto_generate: boolean;
  };
  tokens: { github: boolean; gitee: boolean };
}

export interface ExampleRepo {
  url: string;
  label: string;
  platform: Platform;
  highlight: string;
}

export interface ScanStart {
  job_id: string;
  status: JobStatus;
}

export interface ScanJob {
  job_id: string;
  status: JobStatus;
  stage: string;
  stage_label: string;
  message: string;
  progress: number;
  url: string;
  report_id: string | null;
  cached: boolean;
  error_code: string | null;
  error_message: string | null;
  retry_after: number | null;
  elapsed_ms: number;
  created_at: string;
  updated_at: string;
}

export interface ReportSummary {
  id: string;
  platform: Platform;
  full_name: string;
  branch: string;
  commit_short_sha: string;
  total: number;
  grade: string;
  analyzed_at: string;
  cached: boolean;
}

export interface RepoInfo {
  platform: Platform;
  owner: string;
  name: string;
  full_name: string;
  html_url: string;
  default_branch: string;
  description: string | null;
  stars: number;
  forks: number;
  language: string | null;
  license: string | null;
  archived: boolean;
  private: boolean;
  pushed_at: string | null;
  size_kb: number | null;
}

export interface CommitInfo {
  sha: string;
  short_sha: string;
  branch: string;
  message: string;
  author: string;
  date: string | null;
  url: string;
  source: string;
  archive_ref: string;
  snapshot_warning: string | null;
}

export interface SectionCheck {
  key: string;
  label: string;
  present: boolean;
}

export interface ReadmeSection {
  present: boolean;
  path: string | null;
  chars: number;
  lines: number;
  headings: string[];
  code_blocks: number;
  images: number;
  badges: number;
  sections: SectionCheck[];
  has_install: boolean;
  has_usage: boolean;
  has_config: boolean;
  has_api: boolean;
  has_license: boolean;
  placeholders: string[];
  score: number;
  summary: string;
}

export interface ManifestInfo {
  path: string;
  ecosystem: string;
  kind: string;
  parse_ok: boolean;
  dependency_count: number;
  dev_dependency_count: number;
  lockfile: string | null;
  issues: string[];
  primary: boolean;
}

export interface DependenciesSection {
  manifests: ManifestInfo[];
  ecosystems: string[];
  lockfiles: string[];
  has_manifest: boolean;
  score: number;
  summary: string;
}

export interface StartupEntry {
  source: string;
  path: string | null;
  command: string;
  verified: boolean;
  detail: string;
}

export interface StartupSection {
  entries: StartupEntry[];
  documented_commands: string[];
  env_vars: string[];
  env_example: boolean;
  has_docker: boolean;
  has_compose: boolean;
  has_procfile: boolean;
  has_makefile: boolean;
  suggested_command: string | null;
  mismatches: string[];
  score: number;
  summary: string;
}

export interface WindowsScriptInfo {
  path: string;
  extension: string;
  size: number;
  purpose: string;
  referenced: boolean;
  flags: string[];
  severity: Severity;
}

export interface WindowsSection {
  files: WindowsScriptInfo[];
  count: number;
  only_windows_start: boolean;
  penalty: number;
  summary: string;
}

export interface PathFinding {
  rule_id: string;
  kind: string;
  path: string;
  line: number;
  snippet: string;
  severity: Severity;
  scope: string;
  confidence: string;
}

export interface PathsSection {
  findings: PathFinding[];
  counts_by_rule: Record<string, number>;
  counts_by_severity: Record<string, number>;
  penalty: number;
  summary: string;
}

export interface SecretFinding {
  rule_id: string;
  kind: string;
  path: string;
  line: number;
  masked: string;
  severity: Severity;
  confidence: string;
  in_env_file: boolean;
  fingerprint: string;
}

export interface SecretsSection {
  findings: SecretFinding[];
  counts_by_severity: Record<string, number>;
  env_files: string[];
  gitignore_env: boolean;
  score: number;
  summary: string;
}

export interface ReportSections {
  readme: ReadmeSection;
  dependencies: DependenciesSection;
  startup: StartupSection;
  windows: WindowsSection;
  paths: PathsSection;
  secrets: SecretsSection;
}

export interface Risk {
  id: string;
  rule_id: string;
  dimension: DimensionKey;
  category: string;
  severity: Severity;
  title: string;
  description: string;
  file: string | null;
  line: number | null;
  evidence: string | null;
  occurrences: number;
  recommendation: string;
  source_url: string | null;
  confidence: string;
  blocking: boolean;
}

export interface DimensionScore {
  key: DimensionKey;
  name: string;
  score: number;
  weight: number;
  weighted: number;
  status: string;
  summary: string;
  reasons: string[];
  risk_ids: string[];
}

export interface ScoreInfo {
  total: number;
  raw_total: number;
  grade: string;
  label: string;
  capped: boolean;
  cap_reason: string[];
  dimensions: DimensionScore[];
  formula_version: string;
  fingerprint: string;
}

export interface AiBlocker {
  title: string;
  why: string;
  fix: string;
  severity: Severity;
}

export interface AiQuickWin {
  action: string;
  effect: string;
}

export interface AiStep {
  step: number;
  detail: string;
}

export interface AiAdvice {
  status: AiStatus;
  provider: string | null;
  model: string | null;
  generated_at: string | null;
  latency_ms: number | null;
  summary: string;
  reference_score: number | null;
  score_reason: string;
  blockers: AiBlocker[];
  quick_wins: AiQuickWin[];
  integration_plan: AiStep[];
  caveats: string[];
  error: string | null;
}

export interface UpdateInfo {
  previous_commit: string | null;
  previous_report_id: string | null;
  has_previous: boolean;
  note: string | null;
}

export interface SnapshotInfo {
  compressed_bytes: number;
  extracted_bytes: number;
  files_total: number;
  files_scanned: number;
  files_skipped: number;
  text_bytes_scanned: number;
  truncated: boolean;
  warnings: string[];
}

export interface LanguageStat {
  name: string;
  files: number;
}

export interface ProjectInfo {
  languages: LanguageStat[];
  has_ci: boolean;
  has_tests: boolean;
  has_license: boolean;
  has_docker: boolean;
  file_count: number;
}

export interface Report {
  id: string;
  schema_version: string;
  tool_version: string;
  rules_version: string;
  platform: Platform;
  repo: RepoInfo;
  commit: CommitInfo;
  analyzed_at: string;
  duration_ms: number;
  cached: boolean;
  score: ScoreInfo;
  sections: ReportSections;
  risks: Risk[];
  suggestions: string[];
  ai: AiAdvice;
  update: UpdateInfo;
  limits: SnapshotInfo;
  project: ProjectInfo;
}

export interface UpdateCheck {
  status: "up_to_date" | "update_available" | "unknown";
  current_commit: string;
  latest_commit: string | null;
  latest_short: string | null;
  message: string;
  retry_after: number | null;
}

export type SeverityFilter = Severity | "all";
export type DimensionFilter = DimensionKey | "all";
