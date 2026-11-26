import { Calculator, Info, ShieldAlert, X } from "lucide-react";
import { useEffect, useRef } from "react";
import {
  DIMENSION_META,
  DIMENSION_ORDER,
  GRADE_META,
  cx,
} from "../lib/format";
import type { Report } from "../lib/types";
import { Button } from "./ui";

const GRADE_ROWS = [
  { grade: "A", range: "90–100", label: "可直接接入" },
  { grade: "B", range: "80–89", label: "小修后可接入" },
  { grade: "C", range: "70–79", label: "需治理后接入" },
  { grade: "D", range: "60–69", label: "风险较高，先整改" },
  { grade: "F", range: "< 60", label: "存在阻断项，暂不建议接入" },
];

export function ScoreMethod({
  open,
  report,
  onClose,
}: {
  open: boolean;
  report: Report;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/65 p-0 backdrop-blur-sm sm:items-center sm:p-6"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="score-method-title"
        className="panel max-h-[88vh] w-full max-w-2xl overflow-auto rounded-b-none p-5 sm:rounded-2xl sm:p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-line bg-surface-2 text-accent">
              <Calculator size={17} aria-hidden="true" />
            </span>
            <div>
              <h2 id="score-method-title" className="text-base font-semibold text-ink">
                评分方法与局限性
              </h2>
              <p className="mt-0.5 text-[11px] text-muted">
                确定性规则引擎 · 规则版本 {report.rules_version} · 公式{" "}
                {report.score.formula_version}
              </p>
            </div>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted transition-colors hover:bg-surface-2 hover:text-ink"
            aria-label="关闭评分说明"
          >
            <X size={17} aria-hidden="true" />
          </button>
        </div>

        <div className="mt-5 rounded-xl border border-line bg-[#0a1424]/60 p-4">
          <p className="text-[10px] uppercase tracking-[0.14em] text-faint">公式</p>
          <p className="mt-1.5 font-mono text-xs leading-6 text-ink">
            total = round( Σ(dimension_score × weight) / 100 )
          </p>
          <p className="mt-1 text-[10px] leading-5 text-muted">
            五个维度均参与计算，不做 N/A 重归一；无源码 / 无清单 / 无启动方式会在对应维度得 0 分。
          </p>
        </div>

        <div className="mt-4 overflow-hidden rounded-xl border border-line">
          <table className="w-full text-left text-[11px]">
            <thead className="bg-[#0a1424]/80 text-[10px] uppercase tracking-[0.1em] text-faint">
              <tr>
                <th className="px-3 py-2 font-medium">维度</th>
                <th className="px-3 py-2 font-medium">权重</th>
                <th className="px-3 py-2 font-medium">本次得分</th>
                <th className="px-3 py-2 font-medium">加权</th>
                <th className="px-3 py-2 font-medium">状态</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/70">
              {DIMENSION_ORDER.map((key) => {
                const dimension = report.score.dimensions.find((item) => item.key === key);
                if (!dimension) return null;
                return (
                  <tr key={key} className="text-muted">
                    <td className="px-3 py-2.5">
                      <span className="text-ink">{DIMENSION_META[key].label}</span>
                      <span className="ml-1.5 text-[10px] text-faint">
                        {DIMENSION_META[key].short}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 font-mono">{dimension.weight}%</td>
                    <td className="px-3 py-2.5 font-mono">{dimension.score}</td>
                    <td className="px-3 py-2.5 font-mono">{dimension.weighted}</td>
                    <td className="px-3 py-2.5">{dimension.status}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-[10px] uppercase tracking-[0.14em] text-faint">等级</p>
            <div className="mt-2 space-y-1.5">
              {GRADE_ROWS.map((row) => {
                const meta = GRADE_META[row.grade];
                return (
                  <div
                    key={row.grade}
                    className="flex items-center justify-between gap-2 text-[11px]"
                  >
                    <span className="flex items-center gap-2">
                      <span
                        className={cx(
                          "inline-flex h-5 w-5 items-center justify-center rounded border font-mono text-[10px]",
                          meta.border,
                          meta.bg,
                          meta.text,
                        )}
                      >
                        {row.grade}
                      </span>
                      <span className="text-muted">{row.label}</span>
                    </span>
                    <span className="font-mono text-[10px] text-faint">{row.range}</span>
                  </div>
                );
              })}
            </div>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.14em] text-faint">红线封顶</p>
            <div className="mt-2 space-y-2 text-[11px] leading-5 text-muted">
              <p className="flex items-start gap-1.5">
                <ShieldAlert size={13} className="mt-0.5 shrink-0 text-critical" aria-hidden="true" />
                critical 级密钥/私钥：总分封顶 49（F）
              </p>
              <p className="flex items-start gap-1.5">
                <ShieldAlert size={13} className="mt-0.5 shrink-0 text-high" aria-hidden="true" />
                high 级敏感信息：总分封顶 69（D）
              </p>
              <p className="flex items-start gap-1.5">
                <Info size={13} className="mt-0.5 shrink-0 text-accent-2" aria-hidden="true" />
                AI 参考分独立展示，不参与主评分；AI 不修改风险事实。
              </p>
            </div>
          </div>
        </div>

        <div className="mt-5 rounded-xl border border-line bg-[#0a1424]/50 p-4 text-[10px] leading-5 text-muted">
          <p className="text-[11px] font-medium text-ink">已知局限</p>
          <ul className="mt-1.5 space-y-1">
            <li>· 静态启发式扫描，无法理解业务语境；路径与泛化凭据可能仍需人工复核。</li>
            <li>· 仅支持公开 GitHub / Gitee 仓库，不执行仓库代码，不做依赖漏洞库比对。</li>
            <li>· 归档体积、文件数与文本扫描量有上限；超限时会截断并在报告中标明。</li>
            <li>· 本报告指纹：<span className="font-mono">{report.score.fingerprint}</span>（不含 AI 与时间）。</li>
          </ul>
        </div>

        <div className="mt-5 flex justify-end">
          <Button variant="secondary" onClick={onClose}>
            知道了
          </Button>
        </div>
      </div>
    </div>
  );
}
