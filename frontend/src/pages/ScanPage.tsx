import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Clock,
  GitBranch,
  Loader2,
  Lock,
  RefreshCw,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, errorMessage } from "../lib/api";
import { cx, formatDuration } from "../lib/format";
import type { ScanJob } from "../lib/types";
import {
  Button,
  ErrorNotice,
  PageContainer,
  Panel,
  Pill,
  Spinner,
} from "../components/ui";

const STAGES = [
  { key: "validating", label: "解析仓库链接" },
  { key: "metadata", label: "获取仓库元数据" },
  { key: "downloading", label: "下载仓库快照" },
  { key: "extracting", label: "安全解压快照" },
  { key: "indexing", label: "建立文件索引" },
  { key: "analyzing", label: "执行六类检测" },
  { key: "scoring", label: "计算评分与风险" },
  { key: "saving", label: "写入报告缓存" },
];

function stageIndex(stage: string): number {
  if (stage === "done") return STAGES.length;
  const index = STAGES.findIndex((item) => item.key === stage);
  return index < 0 ? 0 : index;
}

export function ScanPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<ScanJob | null>(null);
  const [error, setError] = useState("");
  const [retrying, setRetrying] = useState(false);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    let delay = 650;
    let failures = 0;

    async function poll() {
      if (!jobId || cancelled) return;
      try {
        const next = await api.getJob(jobId);
        if (cancelled) return;
        failures = 0;
        setJob(next);
        setError("");
        if (next.status === "succeeded" && next.report_id) {
          navigate(`/report/${next.report_id}`, { replace: true });
          return;
        }
        if (next.status === "failed") {
          return;
        }
        if (next.elapsed_ms > 12_000) delay = 1200;
        pollRef.current = window.setTimeout(poll, delay);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setJob(null);
          setError(errorMessage(err));
          return;
        }
        failures += 1;
        setError(
          failures >= 5
            ? `连接中断，仍在自动重试（第 ${failures} 次）…`
            : `连接中断，正在自动重试（${failures}/5）…`,
        );
        const retryDelay = Math.min(5000, 700 + failures * 500);
        pollRef.current = window.setTimeout(poll, retryDelay);
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (pollRef.current) window.clearTimeout(pollRef.current);
    };
  }, [jobId, navigate]);

  async function handleRetry() {
    if (!job?.url) return;
    setRetrying(true);
    try {
      const next = await api.startScan(job.url, true);
      navigate(`/scan/${next.job_id}`, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
      setRetrying(false);
    }
  }

  const progress = job?.progress ?? 0;
  const currentStage = stageIndex(job?.stage || "queued");
  const failed = job?.status === "failed" || Boolean(error && !job);
  const isQueued = job?.status === "queued";

  return (
    <PageContainer className="max-w-4xl py-10 lg:py-14">
      <div className="mb-6 flex items-center justify-between gap-3">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs text-muted transition-colors hover:text-ink"
        >
          <ArrowLeft size={14} aria-hidden="true" />
          返回首页
        </Link>
        <Pill tone={failed ? "danger" : "accent"}>
          {failed ? (
            <AlertTriangle size={11} aria-hidden="true" />
          ) : (
            <span className="h-1.5 w-1.5 rounded-full bg-accent animate-soft-pulse" />
          )}
          {failed ? "体检失败" : isQueued ? "排队中" : "正在体检"}
        </Pill>
      </div>

      <Panel className="overflow-hidden">
        <div className="border-b border-line/80 px-5 py-5 sm:px-7">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-surface-2 text-muted">
              <GitBranch size={15} aria-hidden="true" />
            </span>
            <p className="min-w-0 break-all font-mono text-xs text-muted sm:text-sm">
              {job?.url || "正在获取仓库信息…"}
            </p>
          </div>
          <div className="mt-5 flex items-end justify-between gap-4">
            <div>
              <p className="text-[11px] uppercase tracking-[0.18em] text-faint">
                Progress
              </p>
              <p className="mt-1 text-2xl font-semibold text-ink">
                {failed ? "未能完成" : job?.stage_label || "准备中"}
              </p>
              <p className="mt-1 min-h-[20px] text-xs text-muted">
                {error || job?.message || "正在连接仓库平台…"}
              </p>
            </div>
            <div className="text-right">
              <p className="font-mono text-3xl font-semibold tabular-nums text-ink">
                {Math.max(0, Math.min(100, progress))}%
              </p>
              <p className="mt-1 inline-flex items-center gap-1 text-[11px] text-faint">
                <Clock size={11} aria-hidden="true" />
                {formatDuration(job?.elapsed_ms || 0)}
              </p>
            </div>
          </div>
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-[#091224]">
            <div
              className={cx(
                "h-full rounded-full transition-[width] duration-500",
                failed
                  ? "bg-critical"
                  : "bg-[linear-gradient(90deg,#22d3ee,#34d399)]",
              )}
              style={{ width: `${Math.max(2, Math.min(100, progress))}%` }}
            />
          </div>
        </div>

        {failed ? (
          <div className="space-y-4 px-5 py-6 sm:px-7">
            <ErrorNotice
              title={job?.error_code ? `错误码：${job.error_code}` : "体检没有完成"}
              message={
                job?.error_message ||
                error ||
                "请稍后重试；如果持续失败，检查链接是否为公开仓库。"
              }
            />
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" onClick={handleRetry} disabled={retrying}>
                {retrying ? <Spinner /> : <RefreshCw size={14} aria-hidden="true" />}
                重新体检
              </Button>
              <Link to="/">
                <Button variant="secondary">返回首页</Button>
              </Link>
            </div>
            {job?.retry_after ? (
              <p className="text-[11px] leading-5 text-medium">
                平台建议约 {job.retry_after} 秒后重试；配置 Token 可显著提高限额。
              </p>
            ) : null}
            {job?.error_code === "RATE_LIMITED" ? (
              <p className="text-[11px] leading-5 text-muted">
                提示：在项目根目录的 <code className="font-mono">.env</code> 配置{" "}
                <code className="font-mono">GITHUB_TOKEN</code> 或{" "}
                <code className="font-mono">GITEE_TOKEN</code> 后重启服务，可显著提高 API 限额。
              </p>
            ) : null}
          </div>
        ) : (
          <div className="grid gap-6 px-5 py-6 sm:px-7 md:grid-cols-[1fr_260px]">
            <ol className="space-y-3">
              {STAGES.map((stage, index) => {
                const done = currentStage > index || job?.stage === "done";
                const active = currentStage === index && job?.status === "running";
                return (
                  <li key={stage.key} className="flex items-center gap-3">
                    <span
                      className={cx(
                        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[10px]",
                        done
                          ? "border-accent/40 bg-accent/10 text-accent"
                          : active
                            ? "border-accent-2/50 bg-accent-2/10 text-accent-2"
                            : "border-line bg-surface-2 text-faint",
                      )}
                    >
                      {done ? (
                        <Check size={13} aria-hidden="true" />
                      ) : active ? (
                        <Loader2 size={13} className="animate-spin" aria-hidden="true" />
                      ) : (
                        index + 1
                      )}
                    </span>
                    <span
                      className={cx(
                        "text-xs",
                        done ? "text-muted" : active ? "text-ink" : "text-faint",
                      )}
                    >
                      {stage.label}
                    </span>
                    {active ? (
                      <span className="text-[10px] text-accent-2">进行中</span>
                    ) : null}
                  </li>
                );
              })}
            </ol>
            <div className="space-y-3">
              <div className="rounded-xl border border-line bg-[#0a1424]/70 p-4">
                <p className="flex items-center gap-2 text-xs font-medium text-ink">
                  <ShieldCheck size={14} className="text-accent" aria-hidden="true" />
                  只读安全扫描
                </p>
                <p className="mt-2 text-[11px] leading-5 text-muted">
                  工具只下载归档并静态分析，不会安装依赖、执行脚本或把仓库代码发送到 AI。
                </p>
              </div>
              <div className="rounded-xl border border-line bg-[#0a1424]/70 p-4">
                <p className="flex items-center gap-2 text-xs font-medium text-ink">
                  <Lock size={14} className="text-accent-2" aria-hidden="true" />
                  密钥脱敏
                </p>
                <p className="mt-2 text-[11px] leading-5 text-muted">
                  命中的敏感值只保留前后几位用于定位，报告、导出与日志都不会包含明文。
                </p>
              </div>
              <div className="rounded-xl border border-line bg-[#0a1424]/70 p-4">
                <p className="flex items-center gap-2 text-xs font-medium text-ink">
                  <Terminal size={14} className="text-muted" aria-hidden="true" />
                  通常耗时
                </p>
                <p className="mt-2 text-[11px] leading-5 text-muted">
                  小型仓库约 5–15 秒；Gitee 归档被反爬拦截时会自动回退到浅克隆。
                </p>
              </div>
            </div>
          </div>
        )}
      </Panel>

      <p className="mt-4 text-center text-[11px] text-faint">
        报告会固定记录本次扫描的 commit，可在报告中随时检查上游是否有新提交。
      </p>
    </PageContainer>
  );
}
