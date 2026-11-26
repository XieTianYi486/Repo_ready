import { DIMENSION_META, cx } from "../lib/format";
import type { DimensionScore } from "../lib/types";

export function DimensionBars({ dimensions }: { dimensions: DimensionScore[] }) {
  return (
    <div className="space-y-1">
      {dimensions.map((dimension) => {
        const meta = DIMENSION_META[dimension.key];
        const score = Math.max(0, Math.min(100, dimension.score));
        return (
          <div
            key={dimension.key}
            className="group relative rounded-lg px-2 py-2.5 transition-colors hover:bg-surface-2/60 focus-visible:bg-surface-2/60"
            tabIndex={0}
            aria-label={`${meta.label} ${score} 分，权重 ${dimension.weight}%，${dimension.status}`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2">
                <span className="w-[72px] shrink-0 truncate text-xs text-muted">
                  {meta.short}
                </span>
                <span className="hidden text-[10px] text-faint sm:inline">
                  {dimension.weight}%
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={cx(
                    "text-[10px]",
                    score >= 70
                      ? "text-muted"
                      : score >= 50
                        ? "text-medium"
                        : "text-critical",
                  )}
                >
                  {dimension.status}
                </span>
                <span className="w-8 text-right font-mono text-sm font-semibold tabular-nums text-ink">
                  {score}
                </span>
              </div>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#0a1424]">
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,#1fa97d,#34d399)] transition-[width] duration-700"
                style={{ width: `${Math.max(score > 0 ? 2 : 0, score)}%` }}
              />
            </div>
            <div className="pointer-events-none absolute left-2 right-2 top-[calc(100%-4px)] z-30 hidden rounded-lg border border-line bg-[#0a1424] p-3 shadow-2xl group-hover:block group-focus-within:block">
              <p className="text-[11px] font-medium text-ink">
                {meta.label} · {meta.description}
              </p>
              <ul className="mt-1.5 space-y-1">
                {dimension.reasons.slice(0, 4).map((reason, index) => (
                  <li key={`${dimension.key}-${index}`} className="text-[10px] leading-4 text-muted">
                    · {reason}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        );
      })}
    </div>
  );
}
