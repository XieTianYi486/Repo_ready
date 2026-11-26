import {
  AlertOctagon,
  AlertTriangle,
  CircleAlert,
  Info,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { SEVERITY_META, cx } from "../lib/format";
import type { Severity, SeverityFilter } from "../lib/types";

const TILE_ICONS: Record<Severity, LucideIcon> = {
  critical: AlertOctagon,
  high: AlertTriangle,
  medium: CircleAlert,
  low: Info,
  info: ShieldCheck,
};

export function SeverityTiles({
  counts,
  active,
  onSelect,
}: {
  counts: Record<Severity, number>;
  active: SeverityFilter;
  onSelect: (value: SeverityFilter) => void;
}) {
  const total = Object.values(counts).reduce((sum, value) => sum + value, 0);
  const items: Array<{ key: SeverityFilter; label: string; count: number }> = [
    { key: "all", label: "全部", count: total },
    ...(
      ["critical", "high", "medium", "low", "info"] as Severity[]
    ).map((severity) => ({
      key: severity,
      label: SEVERITY_META[severity].label,
      count: counts[severity],
    })),
  ];

  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
      {items.map((item) => {
        const isActive = active === item.key;
        const isAll = item.key === "all";
        const meta = isAll ? null : SEVERITY_META[item.key as Severity];
        const Icon = isAll ? ShieldCheck : TILE_ICONS[item.key as Severity];
        return (
          <button
            key={item.key}
            type="button"
            onClick={() => onSelect(item.key)}
            className={cx(
              "rounded-xl border px-3 py-2.5 text-left transition-colors",
              isActive
                ? "border-accent/40 bg-surface-2"
                : "border-line bg-surface/50 hover:border-line/120 hover:bg-surface-2/60",
            )}
            aria-pressed={isActive}
          >
            <span className="flex items-center gap-1.5 text-[10px] text-muted">
              <Icon
                size={12}
                style={meta ? { color: meta.hex } : undefined}
                aria-hidden="true"
              />
              {item.label}
            </span>
            <span
              className="mt-1 block font-mono text-xl font-semibold tabular-nums"
              style={meta ? { color: meta.hex } : undefined}
            >
              {item.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
