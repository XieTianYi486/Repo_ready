import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Lightbulb,
  ListChecks,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { SEVERITY_META, cx, formatDate } from "../lib/format";
import type { Report } from "../lib/types";
import { Button, EmptyState, ErrorNotice, Panel, Pill, Skeleton, Spinner } from "./ui";

function RuleSuggestions({ suggestions }: { suggestions: string[] }) {
  if (!suggestions.length) return null;
  return (
    <div className="mt-4 rounded-xl border border-line bg-[#0a1424]/50 p-4">
      <p className="flex items-center gap-2 text-xs font-medium text-ink">
        <ListChecks size={14} className="text-accent-2" aria-hidden="true" />
        规则建议（无需 AI）
      </p>
      <ul className="mt-2 space-y-1.5">
        {suggestions.map((suggestion) => (
          <li key={suggestion} className="flex items-start gap-2 text-[11px] leading-5 text-muted">
            <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-accent-2" />
            {suggestion}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AiAdvicePanel({
  report,
  generating,
  aiEnabled,
  onGenerate,
}: {
  report: Report;
  generating: boolean;
  aiEnabled: boolean;
  onGenerate: () => void;
}) {
  const ai = report.ai;
  const isReady = ai.status === "ready";
  const isError = ai.status === "error";
  const isDisabled = ai.status === "disabled";
  const isPending = generating || ai.status === "pending";
  const needsGenerate = ai.status === "not_generated" && !generating;
  const canGenerate =
    aiEnabled && (ai.status === "not_generated" || ai.status === "disabled") && !generating;

  return (
    <Panel className="p-5" id="ai-advice">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-accent-2/20 bg-accent-2/8 text-accent-2">
            <Sparkles size={16} aria-hidden="true" />
          </span>
          <div>
            <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
              AI 接入建议
              <Pill tone="info">不影响主评分</Pill>
            </h3>
            <p className="mt-0.5 text-[11px] leading-5 text-muted">
              基于脱敏后的体检摘要生成；只发结构信息，不发源码全文与明文密钥。
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isReady ? (
            <Pill tone="accent">
              <Bot size={11} aria-hidden="true" />
              {ai.provider} · {ai.model}
            </Pill>
          ) : null}
          {canGenerate ? (
            <Button size="sm" variant="secondary" onClick={onGenerate} disabled={generating}>
              {generating ? <Spinner /> : <Sparkles size={12} aria-hidden="true" />}
              生成 AI 建议
            </Button>
          ) : null}
          {isPending ? (
            <Button size="sm" variant="secondary" disabled>
              <Spinner />
              生成中
            </Button>
          ) : null}
        </div>
      </div>

      {isDisabled ? (
        <div className="mt-4">
          {aiEnabled ? (
            <div className="rounded-xl border border-accent-2/20 bg-accent-2/5 p-4">
              <p className="flex items-center gap-2 text-xs font-medium text-ink">
                <Sparkles size={14} className="text-accent-2" aria-hidden="true" />
                AI 已启用，但此报告生成时尚未配置 AI
              </p>
              <p className="mt-1.5 text-[11px] leading-5 text-muted">
                点击右上角「生成 AI 建议」即可为这份旧报告补生成建议；主评分与指纹不会改变。
              </p>
            </div>
          ) : (
            <>
              <EmptyState
                icon={Bot}
                title="AI 建议未启用"
                description="在 .env 中配置 AI_PROVIDER 与 Anthropic / OpenAI 兼容 Key 后重启服务即可启用。核心体检与规则建议不受影响。"
              />
              <div className="mt-3 rounded-lg border border-line bg-[#0a1424]/60 p-3 font-mono text-[10px] leading-5 text-muted">
                AI_PROVIDER=auto
                <br />
                ANTHROPIC_API_KEY=...
                <br />
                # 或 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
              </div>
            </>
          )}
          <RuleSuggestions suggestions={report.suggestions} />
        </div>
      ) : null}

      {isError ? (
        <div className="mt-4 space-y-3">
          <ErrorNotice
            title="AI 建议生成失败"
            message={ai.error || "AI 服务暂时不可用，可稍后重试。"}
            action={
              <Button size="sm" variant="secondary" onClick={onGenerate} disabled={generating}>
                {generating ? <Spinner /> : <RefreshCw size={12} aria-hidden="true" />}
                重试
              </Button>
            }
          />
          <RuleSuggestions suggestions={report.suggestions} />
        </div>
      ) : null}

      {needsGenerate && aiEnabled ? (
        <div className="mt-4 rounded-xl border border-line bg-[#0a1424]/50 p-4">
          <p className="flex items-center gap-2 text-xs font-medium text-ink">
            <Sparkles size={14} className="text-accent-2" aria-hidden="true" />
            尚未生成 AI 建议
          </p>
          <p className="mt-1.5 text-[11px] leading-5 text-muted">
            点击右上角“生成 AI 建议”，AI 会基于已脱敏的体检摘要给出阻断项、快速收益与接入步骤；不影响确定性主评分。
          </p>
        </div>
      ) : null}

      {isPending ? (
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-2 text-xs text-muted">
            <Spinner />
            AI 正在阅读脱敏摘要并生成建议…
          </div>
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <div className="grid gap-2 sm:grid-cols-2">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
        </div>
      ) : null}

      {isReady ? (
        <div className="mt-5 space-y-5">
          <div className="grid gap-3 sm:grid-cols-[220px_1fr]">
            <div className="rounded-xl border border-accent-2/20 bg-accent-2/5 p-4">
              <p className="text-[10px] uppercase tracking-[0.12em] text-accent-2/80">
                AI 参考分
              </p>
              <div className="mt-1 flex items-end gap-1">
                <span className="font-mono text-4xl font-semibold text-accent-2">
                  {ai.reference_score ?? "—"}
                </span>
                <span className="pb-1 text-[10px] text-faint">/ 100</span>
              </div>
              <p className="mt-1 text-[10px] leading-4 text-faint">
                仅供参考，不参与确定性评分
              </p>
            </div>
            <div className="rounded-xl border border-line bg-[#0a1424]/50 p-4">
              {ai.summary ? (
                <p className="text-xs leading-6 text-muted">{ai.summary}</p>
              ) : null}
              {ai.score_reason ? (
                <p className="mt-2 border-t border-line/70 pt-2 text-[11px] leading-5 text-faint">
                  {ai.score_reason}
                </p>
              ) : null}
            </div>
          </div>

          {ai.blockers.length ? (
            <div>
              <p className="mb-2 flex items-center gap-2 text-xs font-medium text-ink">
                <ShieldAlert size={14} className="text-critical" aria-hidden="true" />
                优先阻断项
              </p>
              <div className="space-y-2">
                {ai.blockers.map((blocker, index) => {
                  const meta = SEVERITY_META[blocker.severity] || SEVERITY_META.medium;
                  return (
                    <div
                      key={`${blocker.title}-${index}`}
                      className="rounded-lg border border-line bg-[#0a1424]/50 p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={cx("rounded border px-1.5 py-0.5 text-[10px]", meta.border, meta.bg, meta.text)}
                        >
                          {meta.label}
                        </span>
                        <p className="text-xs font-medium text-ink">{blocker.title}</p>
                      </div>
                      <p className="mt-1.5 text-[11px] leading-5 text-muted">{blocker.why}</p>
                      <p className="mt-1.5 flex items-start gap-1.5 text-[11px] leading-5 text-accent/90">
                        <Lightbulb size={12} className="mt-0.5 shrink-0" aria-hidden="true" />
                        {blocker.fix}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}

          {ai.quick_wins.length ? (
            <div>
              <p className="mb-2 flex items-center gap-2 text-xs font-medium text-ink">
                <CheckCircle2 size={14} className="text-accent" aria-hidden="true" />
                快速收益
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {ai.quick_wins.map((item, index) => (
                  <div
                    key={`${item.action}-${index}`}
                    className="rounded-lg border border-line bg-[#0a1424]/50 p-3"
                  >
                    <p className="text-[11px] font-medium text-ink">{item.action}</p>
                    <p className="mt-1 text-[10px] leading-5 text-muted">{item.effect}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {ai.integration_plan.length ? (
            <div>
              <p className="mb-2 flex items-center gap-2 text-xs font-medium text-ink">
                <ListChecks size={14} className="text-accent-2" aria-hidden="true" />
                接入步骤
              </p>
              <ol className="space-y-2">
                {ai.integration_plan.map((item) => (
                  <li key={`${item.step}-${item.detail}`} className="flex items-start gap-2.5">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-accent-2/25 bg-accent-2/8 font-mono text-[10px] text-accent-2">
                      {item.step}
                    </span>
                    <span className="text-[11px] leading-5 text-muted">{item.detail}</span>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}

          {ai.caveats.length ? (
            <div className="rounded-lg border border-medium/20 bg-medium/5 p-3">
              <p className="text-[10px] uppercase tracking-[0.12em] text-medium">
                注意事项
              </p>
              <ul className="mt-1.5 space-y-1">
                {ai.caveats.map((caveat, index) => (
                  <li key={`${caveat}-${index}`} className="text-[10px] leading-5 text-muted">
                    · {caveat}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-faint">
            <span>{ai.generated_at ? `生成于 ${formatDate(ai.generated_at)}` : ""}</span>
            {ai.latency_ms ? <span>耗时 {Math.round(ai.latency_ms / 100) / 10}s</span> : null}
            <span className="inline-flex items-center gap-1">
              <AlertTriangle size={10} aria-hidden="true" />
              AI 输出经结构校验，但仍建议人工复核
            </span>
          </p>
        </div>
      ) : null}
    </Panel>
  );
}
