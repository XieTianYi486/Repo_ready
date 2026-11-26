import { DIMENSION_META, cx } from "../lib/format";
import type { DimensionScore } from "../lib/types";

export function DimensionCards({
  dimensions,
  onSelect,
}: {
  dimensions: DimensionScore[];
  onSelect?: (key: DimensionScore["key"]) => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {dimensions.map((dimension) => {
        const meta = DIMENSION_META[dimension.key];
        const score = Math.max(0, Math.min(100, dimension.score));
        return (
          <button
            type="button"
            key={dimension.key}
            id={`dim-${dimension.key}`}
            onClick={() => onSelect?.(dimension.key)}
            className="panel-soft group p-4 text-left transition-colors hover:border-accent/25 hover:bg-surface-2/70"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-[10px] uppercase tracking-[0.15em] text-faint">
                  {meta.short}
                </p>
                <p className="mt-1 text-xs font-medium text-ink">{meta.label}</p>
              </div>
              <span
                className={cx(
                  "rounded-full border px-2 py-0.5 text-[10px]",
                  score >= 70
                    ? "border-accent/20 bg-accent/8 text-accent"
                    : score >= 50
                      ? "border-medium/25 bg-medium/8 text-medium"
                      : "border-critical/25 bg-critical/8 text-critical",
                )}
              >
                {dimension.status}
              </span>
            </div>
            <div className="mt-3 flex items-end gap-1">
              <span className="font-mono text-2xl font-semibold tabular-nums text-ink">
                {score}
              </span>
              <span className="pb-1 text-[10px] text-faint">/ 100</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#0a1424]">
              <div
                className="h-full rounded-full bg-accent transition-[width] duration-700"
                style={{ width: `${Math.max(score > 0 ? 2 : 0, score)}%` }}
              />
            </div>
            <p className="mt-2 line-clamp-2 min-h-[32px] text-[10px] leading-4 text-muted">
              {dimension.summary}
            </p>
            <p className="mt-1.5 text-[10px] text-faint">
              权重 {dimension.weight}% · 加权 {dimension.weighted}
            </p>
          </button>
        );
      })}
    </div>
  );
}
