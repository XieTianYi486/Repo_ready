import {
  AlertTriangle,
  ChevronDown,
  ExternalLink,
  Search,
  ShieldAlert,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  DIMENSION_META,
  SEVERITY_META,
  SEVERITY_ORDER,
  confidenceLabel,
  cx,
  riskLocation,
} from "../lib/format";
import type {
  DimensionFilter,
  Risk,
  Severity,
  SeverityFilter,
} from "../lib/types";
import { EmptyState } from "./ui";

function SeverityBadge({ severity }: { severity: Severity }) {
  const meta = SEVERITY_META[severity];
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium",
        meta.border,
        meta.bg,
        meta.text,
      )}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ background: meta.hex }}
        aria-hidden="true"
      />
      {meta.label}
    </span>
  );
}

export function RiskTable({
  risks,
  severityFilter,
  onSeverityFilter,
  dimensionFilter,
  onDimensionFilter,
}: {
  risks: Risk[];
  severityFilter: SeverityFilter;
  onSeverityFilter: (value: SeverityFilter) => void;
  dimensionFilter: DimensionFilter;
  onDimensionFilter: (value: DimensionFilter) => void;
}) {
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(
    risks.find((risk) => risk.blocking)?.id || null,
  );

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return risks.filter((risk) => {
      if (severityFilter !== "all" && risk.severity !== severityFilter) return false;
      if (dimensionFilter !== "all" && risk.dimension !== dimensionFilter)
        return false;
      if (!query) return true;
      const haystack = [
        risk.title,
        risk.description,
        risk.recommendation,
        risk.file || "",
        risk.rule_id,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [risks, severityFilter, dimensionFilter, search]);

  const hasFilters =
    severityFilter !== "all" || dimensionFilter !== "all" || Boolean(search);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="按严重度筛选"
            value={severityFilter}
            onChange={(event) =>
              onSeverityFilter(event.target.value as SeverityFilter)
            }
            className="h-9 rounded-lg border border-line bg-[#0a1424] px-2.5 text-xs text-ink outline-none focus:border-accent/40"
          >
            <option value="all">全部严重度</option>
            {SEVERITY_ORDER.map((severity) => (
              <option key={severity} value={severity}>
                {SEVERITY_META[severity].label}
              </option>
            ))}
          </select>
          <select
            aria-label="按维度筛选"
            value={dimensionFilter}
            onChange={(event) =>
              onDimensionFilter(event.target.value as DimensionFilter)
            }
            className="h-9 rounded-lg border border-line bg-[#0a1424] px-2.5 text-xs text-ink outline-none focus:border-accent/40"
          >
            <option value="all">全部维度</option>
            {Object.entries(DIMENSION_META).map(([key, meta]) => (
              <option key={key} value={key}>
                {meta.label}
              </option>
            ))}
          </select>
          <div className="relative">
            <Search
              size={13}
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-faint"
              aria-hidden="true"
            />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索风险、文件、规则…"
              className="h-9 w-52 rounded-lg border border-line bg-[#0a1424] pl-8 pr-8 text-xs text-ink outline-none placeholder:text-faint focus:border-accent/40"
              aria-label="搜索风险"
            />
            {search ? (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-faint hover:text-ink"
                aria-label="清空搜索"
              >
                <X size={12} aria-hidden="true" />
              </button>
            ) : null}
          </div>
          {hasFilters ? (
            <button
              type="button"
              onClick={() => {
                onSeverityFilter("all");
                onDimensionFilter("all");
                setSearch("");
              }}
              className="text-[11px] text-muted underline-offset-2 hover:text-ink hover:underline"
            >
              清除筛选
            </button>
          ) : null}
        </div>
        <p className="text-[11px] text-faint">
          显示 {filtered.length} / {risks.length} 条风险
        </p>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={ShieldAlert}
          title={risks.length === 0 ? "没有发现需要处理的风险" : "当前筛选没有匹配项"}
          description={
            risks.length === 0
              ? "仓库在六类检测中表现良好。仍建议结合人工审查确认业务语境。"
              : "尝试调整严重度、维度或搜索关键词。"
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-line">
          <div className="hidden grid-cols-[88px_1fr_110px_180px_50px] gap-3 border-b border-line bg-[#0a1424]/80 px-4 py-2.5 text-[10px] uppercase tracking-[0.12em] text-faint md:grid">
            <span>严重度</span>
            <span>风险</span>
            <span>维度</span>
            <span>位置</span>
            <span className="text-right">次数</span>
          </div>
          <div className="divide-y divide-line/70">
            {filtered.map((risk) => {
              const isOpen = expanded === risk.id;
              const meta = SEVERITY_META[risk.severity];
              return (
                <div
                  key={risk.id}
                  className={cx(
                    "group transition-colors",
                    isOpen ? "bg-surface-2/55" : "hover:bg-surface-2/35",
                  )}
                >
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => setExpanded(isOpen ? null : risk.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setExpanded(isOpen ? null : risk.id);
                      }
                    }}
                    className="grid cursor-pointer grid-cols-1 gap-2 px-4 py-3 outline-none md:grid-cols-[88px_1fr_110px_180px_50px] md:items-center md:gap-3"
                    aria-expanded={isOpen}
                  >
                    <div className="flex items-center justify-between md:block">
                      <SeverityBadge severity={risk.severity} />
                      {risk.blocking ? (
                        <span className="ml-2 inline-flex items-center gap-1 rounded border border-critical/25 bg-critical/8 px-1.5 py-0.5 text-[9px] text-critical">
                          <ShieldAlert size={9} aria-hidden="true" />
                          阻断
                        </span>
                      ) : null}
                    </div>
                    <div className="min-w-0">
                      <p className="flex items-start gap-2 text-xs font-medium text-ink">
                        <ChevronDown
                          size={13}
                          className={cx(
                            "mt-0.5 shrink-0 text-faint transition-transform",
                            isOpen ? "rotate-180" : "",
                          )}
                          aria-hidden="true"
                        />
                        <span className="min-w-0 break-words">{risk.title}</span>
                      </p>
                      <p className="mt-1 line-clamp-1 pl-5 text-[10px] text-muted">
                        {risk.description}
                      </p>
                    </div>
                    <div className="hidden md:block">
                      <span className="rounded border border-line bg-surface px-1.5 py-0.5 text-[10px] text-muted">
                        {DIMENSION_META[risk.dimension]?.short || risk.dimension}
                      </span>
                    </div>
                    <div className="hidden min-w-0 md:block">
                      {risk.source_url ? (
                        <a
                          href={risk.source_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(event) => event.stopPropagation()}
                          className="inline-flex max-w-full items-center gap-1 truncate font-mono text-[10px] text-accent-2 hover:text-accent"
                          title={riskLocation(risk)}
                        >
                          <span className="truncate">{riskLocation(risk)}</span>
                          <ExternalLink size={10} aria-hidden="true" />
                        </a>
                      ) : (
                        <span className="font-mono text-[10px] text-faint">
                          {riskLocation(risk)}
                        </span>
                      )}
                    </div>
                    <div className="hidden text-right font-mono text-[10px] text-faint md:block">
                      ×{risk.occurrences}
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-faint md:hidden">
                      <span className="truncate font-mono">
                        {riskLocation(risk)}
                      </span>
                      <span>×{risk.occurrences}</span>
                    </div>
                  </div>
                  {isOpen ? (
                    <div className="space-y-3 border-t border-line/60 px-4 py-4 md:pl-[104px]">
                      <p className="text-xs leading-6 text-muted">
                        {risk.description}
                      </p>
                      <div className="rounded-lg border border-accent/15 bg-accent/5 px-3 py-2">
                        <p className="text-[10px] uppercase tracking-[0.12em] text-accent/80">
                          修复建议
                        </p>
                        <p className="mt-1 text-xs leading-6 text-ink">
                          {risk.recommendation}
                        </p>
                      </div>
                      {risk.evidence ? (
                        <div>
                          <p className="mb-1.5 text-[10px] uppercase tracking-[0.12em] text-faint">
                            脱敏证据
                          </p>
                          <pre className="code-block max-h-40 overflow-auto p-3">
                            {risk.evidence}
                          </pre>
                        </div>
                      ) : null}
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-faint">
                        <span className="font-mono">{risk.rule_id}</span>
                        <span>{confidenceLabel(risk.confidence)}</span>
                        {risk.source_url ? (
                          <a
                            href={risk.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-accent-2 hover:text-accent"
                          >
                            查看源码行
                            <ExternalLink size={10} aria-hidden="true" />
                          </a>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {risks.length > 0 && filtered.length === 0 ? (
        <p className="flex items-center gap-1.5 text-[11px] text-faint">
          <AlertTriangle size={12} aria-hidden="true" />
          调整筛选条件可查看其它风险。
        </p>
      ) : null}
    </div>
  );
}
