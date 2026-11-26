import { AlertTriangle, ShieldCheck } from "lucide-react";
import { gradeMeta } from "../lib/format";
import type { ScoreInfo } from "../lib/types";

export function ScoreRing({ score }: { score: ScoreInfo }) {
  const size = 236;
  const center = size / 2;
  const radius = 92;
  const stroke = 12;
  const circumference = 2 * Math.PI * radius;
  const arcFraction = 0.75;
  const arcLength = circumference * arcFraction;
  const progressLength = arcLength * (Math.max(0, Math.min(100, score.total)) / 100);
  const meta = gradeMeta(score.grade);

  return (
    <div className="flex flex-col items-center">
      <div
        className="relative"
        role="img"
        aria-label={`接入就绪度 ${score.total} 分，${score.grade} 级，${score.label}`}
      >
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <g transform={`rotate(135 ${center} ${center})`}>
            <circle
              cx={center}
              cy={center}
              r={radius}
              fill="none"
              stroke="#17233a"
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={`${arcLength} ${circumference}`}
            />
            <circle
              cx={center}
              cy={center}
              r={radius}
              fill="none"
              stroke={meta.hex}
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={`${Math.max(0.01, progressLength)} ${circumference}`}
              style={{
                filter: `drop-shadow(0 0 7px ${meta.hex}55)`,
                transition: "stroke-dasharray 700ms ease-out",
              }}
            />
          </g>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-sans text-[58px] font-semibold leading-none tracking-tight"
            style={{ color: meta.hex }}
          >
            {score.total}
          </span>
          <span className="mt-1.5 text-[10px] uppercase tracking-[0.22em] text-faint">
            接入就绪度
          </span>
          <span
            className="mt-2 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium"
            style={{
              color: meta.hex,
              borderColor: `${meta.hex}44`,
              background: `${meta.hex}12`,
            }}
          >
            {score.grade === "A" || score.grade === "B" ? (
              <ShieldCheck size={11} aria-hidden="true" />
            ) : (
              <AlertTriangle size={11} aria-hidden="true" />
            )}
            {score.grade} · {meta.label}
          </span>
        </div>
      </div>
      <p className="mt-3 text-center text-xs font-medium text-ink">{score.label}</p>
      <p className="mt-1 text-center text-[10px] text-faint">
        加权得分 {score.total}/100
        {score.capped ? ` · 原始分 ${score.raw_total}` : ""}
      </p>
      {score.capped ? (
        <div className="mt-3 max-w-[240px] rounded-lg border border-critical/25 bg-critical/8 px-3 py-2 text-left text-[10px] leading-4 text-critical">
          {score.cap_reason.map((reason) => (
            <p key={reason}>{reason}</p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
