import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  Clock,
  GitCommitHorizontal,
  Loader2,
  RefreshCw,
} from "lucide-react";
import type { Report, UpdateCheck } from "../lib/types";
import { Button, Pill } from "./ui";

export function UpdateBanner({
  report,
  state,
  checking,
  onCheck,
  onRefresh,
}: {
  report: Report;
  state: UpdateCheck | null;
  checking: boolean;
  onCheck: () => void;
  onRefresh: () => void;
}) {
  const updateAvailable = state?.status === "update_available";
  const unknown = state?.status === "unknown";
  const upToDate = state?.status === "up_to_date";

  return (
    <div
      className={
        updateAvailable
          ? "rounded-xl border border-medium/30 bg-medium/8 px-4 py-3"
          : unknown
            ? "rounded-xl border border-high/25 bg-high/6 px-4 py-3"
            : "rounded-xl border border-line bg-surface/45 px-4 py-3"
      }
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <span className="mt-0.5 text-muted">
            {updateAvailable ? (
              <AlertTriangle size={15} className="text-medium" aria-hidden="true" />
            ) : unknown ? (
              <AlertTriangle size={15} className="text-high" aria-hidden="true" />
            ) : upToDate ? (
              <Check size={15} className="text-accent" aria-hidden="true" />
            ) : (
              <GitCommitHorizontal size={15} aria-hidden="true" />
            )}
          </span>
          <div className="min-w-0">
            <p className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
              <span>当前报告基于</span>
              <span className="rounded border border-line bg-[#0a1424] px-1.5 py-0.5 font-mono text-[10px] text-ink">
                {report.commit.short_sha}
              </span>
              <span>· {report.commit.branch}</span>
              {report.cached ? <Pill tone="neutral">缓存</Pill> : null}
              {report.commit.snapshot_warning ? (
                <Pill tone="warning">快照告警</Pill>
              ) : null}
            </p>
            <p className="mt-1 text-[10px] leading-5 text-faint">
              {state?.message ||
                "检查上游分支 HEAD 是否已更新；检查结果会缓存 5 分钟。"}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {updateAvailable ? (
            <Button size="sm" variant="primary" onClick={onRefresh}>
              <ArrowUpRight size={13} aria-hidden="true" />
              基于新版本重新体检
            </Button>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              onClick={onCheck}
              disabled={checking}
            >
              {checking ? (
                <Loader2 size={13} className="animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw size={13} aria-hidden="true" />
              )}
              {checking ? "检查中" : "检查更新"}
            </Button>
          )}
          {state ? (
            <span className="inline-flex items-center gap-1 text-[10px] text-faint">
              <Clock size={10} aria-hidden="true" />
              {state.status === "up_to_date"
                ? "已是最新"
                : state.status === "update_available"
                  ? `最新 ${state.latest_short}`
                  : "状态未知"}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
