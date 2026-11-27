import {
  ArrowLeft,
  Check,
  ChevronDown,
  Copy,
  Download,
  FileText,
  FolderTree,
  GitBranch,
  GitFork,
  KeyRound,
  ListFilter,
  Monitor,
  Package,
  Play,
  RefreshCw,
  ShieldAlert,
  Star,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AiAdvicePanel } from "../components/AiAdvicePanel";
import { DimensionBars } from "../components/DimensionBars";
import { DimensionCards } from "../components/DimensionCards";
import {
  DependenciesPanel,
  PathsPanel,
  ReadmePanel,
  SecretsPanel,
  StartupPanel,
  WindowsPanel,
} from "../components/ReportPanels";
import { RiskTable } from "../components/RiskTable";
import { ScoreMethod } from "../components/ScoreMethod";
import { ScoreRing } from "../components/ScoreRing";
import { SeverityTiles } from "../components/SeverityTiles";
import { UpdateBanner } from "../components/UpdateBanner";
import {
  Button,
  ErrorNotice,
  PageContainer,
  Panel,
  Pill,
  Skeleton,
} from "../components/ui";
import { api, ApiError, errorMessage } from "../lib/api";
import {
  DIMENSION_META,
  cx,
  formatBytes,
  formatDate,
  formatDuration,
  formatNumber,
  gradeMeta,
  platformLabel,
  severityCounts,
} from "../lib/format";
import type {
  AiAdvice,
  DimensionFilter,
  DimensionKey,
  Health,
  Report,
  SeverityFilter,
  UpdateCheck,
} from "../lib/types";

type TabKey =
  | "readme"
  | "dependencies"
  | "startup"
  | "windows"
  | "paths"
  | "secrets";

const TAB_DEFS: Array<{
  key: TabKey;
  label: string;
  icon: typeof FileText;
}> = [
  { key: "readme", label: "README", icon: FileText },
  { key: "dependencies", label: "依赖", icon: Package },
  { key: "startup", label: "启动", icon: Play },
  { key: "windows", label: "Windows 脚本", icon: Monitor },
  { key: "paths", label: "硬编码路径", icon: FolderTree },
  { key: "secrets", label: "密钥", icon: KeyRound },
];

function ReportSkeleton() {
  return (
    <PageContainer className="py-10">
      <Skeleton className="h-4 w-32" />
      <div className="mt-4 space-y-4">
        <Panel className="p-6">
          <Skeleton className="h-7 w-2/5" />
          <Skeleton className="mt-3 h-4 w-3/5" />
          <div className="mt-8 grid gap-6 lg:grid-cols-[260px_1fr]">
            <Skeleton className="mx-auto h-56 w-56 rounded-full" />
            <div className="space-y-3">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-5/6" />
            </div>
          </div>
        </Panel>
        <Panel className="p-6">
          <Skeleton className="h-5 w-32" />
          <div className="mt-4 space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        </Panel>
      </div>
    </PageContainer>
  );
}

export function ReportPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<Report | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
  const [dimensionFilter, setDimensionFilter] = useState<DimensionFilter>("all");
  const [activeTab, setActiveTab] = useState<TabKey>("readme");
  const [methodOpen, setMethodOpen] = useState(false);
  const [updateState, setUpdateState] = useState<UpdateCheck | null>(null);
  const [checkingUpdates, setCheckingUpdates] = useState(false);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [toast, setToast] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const aiTriggered = useRef<string | null>(null);
  const updateTriggered = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!reportId) {
      setError("报告 ID 缺失");
      setLoading(false);
      return;
    }
    setLoading(true);
    api
      .getReport(reportId)
      .then((data) => {
        if (cancelled) return;
        setReport(data);
        document.title = `${data.repo.full_name} · RepoReady 体检报告`;
      })
      .catch((err) => {
        if (cancelled) return;
        setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reportId]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((data) => {
        if (!cancelled) setHealth(data);
      })
      .catch(() => {
        // Health is optional; manual AI generation still works.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!report || !health) return;
    if (!health.ai.enabled || !health.ai.auto_generate) return;
    if (report.ai.status !== "not_generated") return;
    if (aiTriggered.current === report.id) return;
    aiTriggered.current = report.id;
    void generateAi(report.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report?.id, report?.ai.status, health?.ai.enabled, health?.ai.auto_generate]);

  useEffect(() => {
    if (!report) return;
    if (updateTriggered.current === report.id) return;
    updateTriggered.current = report.id;
    void checkUpdates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report?.id]);

  async function generateAi(id: string) {
    setAiGenerating(true);
    try {
      const ai = await api.generateAi(id);
      setReport((previous) => (previous ? { ...previous, ai } : previous));
    } catch (err) {
      const message = errorMessage(err);
      setReport((previous) =>
        previous
          ? {
              ...previous,
              ai: {
                ...previous.ai,
                status: "error",
                error: message,
              },
            }
          : previous,
      );
    } finally {
      setAiGenerating(false);
    }
  }

  async function checkUpdates() {
    if (!report) return;
    setCheckingUpdates(true);
    try {
      const state = await api.checkUpdates(report.id);
      setUpdateState(state);
    } catch (err) {
      setUpdateState({
        status: "unknown",
        current_commit: report.commit.sha,
        latest_commit: null,
        latest_short: null,
        message: errorMessage(err),
        retry_after:
          err instanceof ApiError && err.status === 429 ? err.retryAfter : null,
      });
    } finally {
      setCheckingUpdates(false);
    }
  }

  async function refreshScan() {
    if (!report) return;
    setRefreshing(true);
    try {
      const job = await api.refresh(report.id);
      navigate(`/scan/${job.job_id}`);
    } catch (err) {
      setToast(errorMessage(err));
      setRefreshing(false);
    }
  }

  async function copyShare() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setToast("分享链接已复制");
    } catch {
      setToast("复制失败，请手动复制地址栏链接");
    }
  }

  const counts = useMemo(
    () =>
      severityCounts(
        report?.risks || [],
      ),
    [report?.risks],
  );

  if (loading) return <ReportSkeleton />;

  if (!report || error) {
    return (
      <PageContainer className="max-w-3xl py-16">
        <ErrorNotice
          title="无法加载报告"
          message={error || "报告不存在或已过期"}
          action={
            <div className="flex gap-2">
              <Link to="/">
                <Button variant="primary">返回首页</Button>
              </Link>
            </div>
          }
        />
      </PageContainer>
    );
  }

  const grade = gradeMeta(report.score.grade);
  const tabCounts: Record<TabKey, string> = {
    readme: `${report.sections.readme.score}`,
    dependencies: `${report.sections.dependencies.score}`,
    startup: `${report.sections.startup.score}`,
    windows: `${report.sections.windows.count}`,
    paths: `${report.sections.paths.findings.length}`,
    secrets: `${report.sections.secrets.findings.length}`,
  };

  function jumpToRisks(nextSeverity: SeverityFilter) {
    setSeverityFilter(nextSeverity);
    document.getElementById("risks")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function selectDimension(key: DimensionKey) {
    setDimensionFilter(key);
    jumpToRisks("all");
  }

  return (
    <div className="pb-16">
      <PageContainer className="pt-7 lg:pt-10">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs text-muted transition-colors hover:text-ink"
          >
            <ArrowLeft size={14} aria-hidden="true" />
            返回首页
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={copyShare}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 text-[11px] text-muted transition-colors hover:text-ink"
            >
              <Copy size={12} aria-hidden="true" />
              复制分享链接
            </button>
            <details className="group relative">
              <summary className="inline-flex h-8 cursor-pointer list-none items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 text-[11px] text-muted transition-colors hover:text-ink [&::-webkit-details-marker]:hidden">
                <Download size={12} aria-hidden="true" />
                导出
                <ChevronDown size={11} aria-hidden="true" />
              </summary>
              <div className="absolute right-0 z-30 mt-1 w-36 overflow-hidden rounded-lg border border-line bg-[#0a1424] py-1 shadow-2xl">
                <a
                  href={api.exportUrl(report.id, "md")}
                  className="block px-3 py-2 text-[11px] text-muted hover:bg-surface-2 hover:text-ink"
                >
                  Markdown 报告
                </a>
                <a
                  href={api.exportUrl(report.id, "json")}
                  className="block px-3 py-2 text-[11px] text-muted hover:bg-surface-2 hover:text-ink"
                >
                  JSON 数据
                </a>
              </div>
            </details>
            <Button
              size="sm"
              variant="secondary"
              onClick={refreshScan}
              disabled={refreshing}
            >
              <RefreshCw
                size={12}
                className={refreshing ? "animate-spin" : ""}
                aria-hidden="true"
              />
              {refreshing ? "创建任务中" : "重新体检"}
            </Button>
          </div>
        </div>

        <Panel className="overflow-hidden">
          <div className="relative px-5 py-5 sm:px-7 sm:py-6">
            <div className="pointer-events-none absolute inset-x-0 top-0 h-32 bg-[radial-gradient(ellipse_at_20%_0%,rgba(52,211,153,0.12),transparent_60%)]" />
            <div className="relative flex flex-wrap items-start justify-between gap-4">
              <div className="flex min-w-0 items-start gap-3">
                <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-line bg-surface-2 text-muted">
                  {report.platform === "gitee" ? (
                    <GitBranch size={20} aria-hidden="true" />
                  ) : (
                    <GitFork size={20} aria-hidden="true" />
                  )}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <a
                      href={report.repo.html_url}
                      target="_blank"
                      rel="noreferrer"
                      className="truncate text-xl font-semibold text-ink hover:text-accent-2 sm:text-2xl"
                    >
                      {report.repo.full_name}
                    </a>
                    <Pill tone="neutral">{platformLabel(report.platform)}</Pill>
                    {report.repo.archived ? <Pill tone="warning">已归档</Pill> : null}
                    {report.cached ? <Pill tone="info">缓存命中</Pill> : null}
                  </div>
                  {report.repo.description ? (
                    <p className="mt-1 line-clamp-2 max-w-2xl text-xs leading-5 text-muted">
                      {report.repo.description}
                    </p>
                  ) : null}
                  <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-muted">
                    <span className="inline-flex items-center gap-1">
                      <Star size={12} aria-hidden="true" />
                      {formatNumber(report.repo.stars)}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <GitFork size={12} aria-hidden="true" />
                      {formatNumber(report.repo.forks)}
                    </span>
                    {report.repo.language ? <span>{report.repo.language}</span> : null}
                    {report.repo.license ? <span>{report.repo.license}</span> : null}
                    <span className="inline-flex items-center gap-1">
                      <GitBranch size={11} aria-hidden="true" />
                      {report.commit.branch}
                    </span>
                    <a
                      href={report.commit.url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded border border-line bg-[#0a1424] px-1.5 py-0.5 font-mono text-[10px] text-accent-2 hover:text-accent"
                      title={report.commit.message}
                    >
                      {report.commit.short_sha}
                    </a>
                    <span>分析于 {formatDate(report.analyzed_at)}</span>
                    <span>耗时 {formatDuration(report.duration_ms)}</span>
                  </div>
                </div>
              </div>
              <div className="flex flex-col items-end gap-2">
                <Pill tone="accent">
                  {report.rules_version} · {report.score.formula_version}
                </Pill>
                <button
                  type="button"
                  onClick={() => setMethodOpen(true)}
                  className="inline-flex items-center gap-1 text-[11px] text-muted underline-offset-2 hover:text-ink hover:underline"
                >
                  <ListFilter size={12} aria-hidden="true" />
                  评分方法
                </button>
              </div>
            </div>
            {report.commit.snapshot_warning ? (
              <div className="relative mt-4 flex items-start gap-2 rounded-lg border border-medium/25 bg-medium/8 px-3 py-2 text-[11px] leading-5 text-medium">
                <ShieldAlert size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
                <p>{report.commit.snapshot_warning}</p>
              </div>
            ) : null}
            {report.update.has_previous ? (
              <p className="relative mt-2 text-[10px] text-faint">
                上一份报告基于{" "}
                <span className="font-mono">
                  {report.update.previous_commit?.slice(0, 7)}
                </span>
                ，本报告基于{" "}
                <span className="font-mono">{report.commit.short_sha}</span>。
              </p>
            ) : null}
          </div>
          <div className="px-5 pb-5 sm:px-7">
            <UpdateBanner
              report={report}
              state={updateState}
              checking={checkingUpdates}
              onCheck={checkUpdates}
              onRefresh={refreshScan}
            />
          </div>
        </Panel>

        <Panel className="mt-4 p-5 sm:p-6" id="overview">
          <div className="grid gap-6 lg:grid-cols-[260px_1fr] lg:items-start">
            <ScoreRing score={report.score} />
            <div>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent/80">
                    Dimensions
                  </p>
                  <h2 className="mt-1 text-base font-semibold text-ink">五维接入就绪度</h2>
                  <p className="mt-1 text-[11px] leading-5 text-muted">
                    条形长度表示得分；悬停或聚焦可查看扣分依据。维度卡提供表格等价视图。
                  </p>
                </div>
                <div
                  className="rounded-lg border px-2.5 py-1.5 text-[11px]"
                  style={{
                    color: grade.hex,
                    borderColor: `${grade.hex}35`,
                    background: `${grade.hex}0f`,
                  }}
                >
                  {grade.label}
                </div>
              </div>
              <div className="mt-4">
                <DimensionBars dimensions={report.score.dimensions} />
              </div>
              <div className="mt-5">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-[10px] uppercase tracking-[0.14em] text-faint">
                    风险分布
                  </p>
                  <p className="text-[10px] text-faint">
                    点击瓦片筛选风险
                  </p>
                </div>
                <SeverityTiles
                  counts={counts}
                  active={severityFilter}
                  onSelect={jumpToRisks}
                />
              </div>
            </div>
          </div>
        </Panel>

        <div className="mt-4">
          <DimensionCards dimensions={report.score.dimensions} onSelect={selectDimension} />
        </div>

        <section className="mt-10 scroll-mt-24" id="risks">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent/80">
                Risks
              </p>
              <h2 className="mt-1 text-lg font-semibold text-ink">主要风险清单</h2>
              <p className="mt-1 text-[11px] text-muted">
                按阻断项、严重度与维度排序；展开可查看脱敏证据、修复建议与源码行。
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Pill tone={counts.critical ? "danger" : counts.high ? "warning" : "accent"}>
                {counts.critical + counts.high} 个高优先级
              </Pill>
              <Pill tone="neutral">共 {report.risks.length} 条</Pill>
            </div>
          </div>
          <Panel className="p-4 sm:p-5">
            <RiskTable
              risks={report.risks}
              severityFilter={severityFilter}
              onSeverityFilter={setSeverityFilter}
              dimensionFilter={dimensionFilter}
              onDimensionFilter={setDimensionFilter}
            />
          </Panel>
        </section>

        <section className="mt-10">
          <div className="mb-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent/80">
              Details
            </p>
            <h2 className="mt-1 text-lg font-semibold text-ink">仓库画像</h2>
            <p className="mt-1 text-[11px] text-muted">
              README、依赖、启动、Windows 脚本、硬编码路径与密钥的完整检测结果。
            </p>
          </div>
          <Panel className="overflow-hidden">
            <div className="no-scrollbar flex overflow-x-auto border-b border-line">
              {TAB_DEFS.map((tab) => {
                const Icon = tab.icon;
                const active = activeTab === tab.key;
                return (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveTab(tab.key)}
                    className={cx(
                      "relative inline-flex shrink-0 items-center gap-1.5 px-4 py-3 text-[11px] transition-colors",
                      active ? "text-ink" : "text-muted hover:text-ink",
                    )}
                    aria-pressed={active}
                  >
                    <Icon size={13} aria-hidden="true" />
                    {tab.label}
                    <span
                      className={cx(
                        "rounded px-1 py-0.5 font-mono text-[9px]",
                        active ? "bg-surface-2 text-accent" : "bg-surface-2/60 text-faint",
                      )}
                    >
                      {tabCounts[tab.key]}
                    </span>
                    {active ? (
                      <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-accent" />
                    ) : null}
                  </button>
                );
              })}
            </div>
            <div className="p-4 sm:p-5">
              {activeTab === "readme" ? <ReadmePanel report={report} /> : null}
              {activeTab === "dependencies" ? <DependenciesPanel report={report} /> : null}
              {activeTab === "startup" ? <StartupPanel report={report} /> : null}
              {activeTab === "windows" ? <WindowsPanel report={report} /> : null}
              {activeTab === "paths" ? <PathsPanel report={report} /> : null}
              {activeTab === "secrets" ? <SecretsPanel report={report} /> : null}
            </div>
          </Panel>
        </section>

        <section className="mt-10">
          <div className="mb-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent/80">
              AI
            </p>
            <h2 className="mt-1 text-lg font-semibold text-ink">接入建议</h2>
            <p className="mt-1 text-[11px] text-muted">
              AI 建议与规则建议并列展示；主评分始终由确定性规则引擎给出。
            </p>
          </div>
          <AiAdvicePanel
            report={report}
            generating={aiGenerating}
            onGenerate={() => generateAi(report.id)}
          />
        </section>

        <section className="mt-10 grid gap-3 lg:grid-cols-3">
          <Panel className="p-5 lg:col-span-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink">扫描范围与限制</h3>
              <Pill tone={report.limits.truncated ? "warning" : "neutral"}>
                {report.limits.truncated ? "已截断" : "完整"}
              </Pill>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 text-[11px] sm:grid-cols-4">
              <div>
                <p className="text-faint">扫描文件</p>
                <p className="mt-0.5 font-mono text-ink">{formatNumber(report.limits.files_scanned)}</p>
              </div>
              <div>
                <p className="text-faint">跳过文件</p>
                <p className="mt-0.5 font-mono text-ink">{formatNumber(report.limits.files_skipped)}</p>
              </div>
              <div>
                <p className="text-faint">压缩体积</p>
                <p className="mt-0.5 font-mono text-ink">{formatBytes(report.limits.compressed_bytes)}</p>
              </div>
              <div>
                <p className="text-faint">文本扫描</p>
                <p className="mt-0.5 font-mono text-ink">{formatBytes(report.limits.text_bytes_scanned)}</p>
              </div>
            </div>
            {report.limits.warnings.length ? (
              <ul className="mt-3 space-y-1 rounded-lg border border-medium/20 bg-medium/5 px-3 py-2 text-[10px] leading-5 text-medium">
                {report.limits.warnings.map((warning) => (
                  <li key={warning}>· {warning}</li>
                ))}
              </ul>
            ) : null}
            <p className="mt-3 text-[10px] leading-5 text-faint">
              仅做静态扫描，不执行仓库代码或安装依赖。归档体积、文件数与文本扫描量存在上限。
            </p>
          </Panel>

          <Panel className="p-5">
            <h3 className="text-sm font-semibold text-ink">工程信号</h3>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {[
                ["CI", report.project.has_ci],
                ["测试", report.project.has_tests],
                ["License", report.project.has_license],
                ["Docker", report.project.has_docker],
              ].map(([label, value]) => (
                <div
                  key={String(label)}
                  className="flex items-center justify-between rounded-lg border border-line bg-[#0a1424]/50 px-2.5 py-2 text-[10px]"
                >
                  <span className="text-muted">{label}</span>
                  <span className={value ? "text-accent" : "text-faint"}>
                    {value ? "有" : "无"}
                  </span>
                </div>
              ))}
            </div>
            {report.project.languages.length ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {report.project.languages.slice(0, 6).map((language) => (
                  <span
                    key={language.name}
                    className="rounded border border-line bg-surface px-1.5 py-0.5 text-[10px] text-muted"
                  >
                    {language.name} · {language.files}
                  </span>
                ))}
              </div>
            ) : null}
            <p className="mt-3 text-[10px] leading-5 text-faint">
              工程信号仅用于展示，不额外影响评分。
            </p>
          </Panel>
        </section>

        <p className="mt-10 text-center text-[10px] leading-5 text-faint">
          RepoReady · 规则 {report.rules_version} · 指纹{" "}
          <span className="font-mono">{report.score.fingerprint}</span> · 评分仅供参考，接入前请结合人工审查
        </p>
      </PageContainer>

      <ScoreMethod
        open={methodOpen}
        report={report}
        onClose={() => setMethodOpen(false)}
      />

      {toast ? (
        <div className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-full border border-line bg-[#0a1424] px-4 py-2 text-xs text-ink shadow-2xl">
          <Check size={13} className="text-accent" aria-hidden="true" />
          {toast}
        </div>
      ) : null}
    </div>
  );
}
