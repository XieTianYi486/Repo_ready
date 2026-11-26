import type {
  DimensionKey,
  Platform,
  ReportSummary,
  Risk,
  Severity,
} from "./types";

export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export const SEVERITY_META: Record<
  Severity,
  { label: string; hex: string; text: string; bg: string; border: string }
> = {
  critical: {
    label: "严重",
    hex: "#F87171",
    text: "text-critical",
    bg: "bg-critical/10",
    border: "border-critical/30",
  },
  high: {
    label: "高",
    hex: "#FB923C",
    text: "text-high",
    bg: "bg-high/10",
    border: "border-high/30",
  },
  medium: {
    label: "中",
    hex: "#FBBF24",
    text: "text-medium",
    bg: "bg-medium/10",
    border: "border-medium/30",
  },
  low: {
    label: "低",
    hex: "#38BDF8",
    text: "text-low",
    bg: "bg-low/10",
    border: "border-low/30",
  },
  info: {
    label: "信息",
    hex: "#94A3B8",
    text: "text-info",
    bg: "bg-info/10",
    border: "border-info/30",
  },
};

export const SEVERITY_ORDER: Severity[] = [
  "critical",
  "high",
  "medium",
  "low",
  "info",
];

export const DIMENSION_META: Record<
  DimensionKey,
  { label: string; short: string; description: string }
> = {
  readme: {
    label: "文档可读性",
    short: "README",
    description: "是否能让接入者快速理解并开始使用",
  },
  dependencies: {
    label: "依赖可安装性",
    short: "依赖",
    description: "依赖清单、锁文件与解析完整性",
  },
  startup: {
    label: "启动可运行性",
    short: "启动",
    description: "是否有明确、可核实的启动路径",
  },
  cross_platform: {
    label: "跨平台接入性",
    short: "跨平台",
    description: "Windows 专用脚本与硬编码路径风险",
  },
  security: {
    label: "安全合规性",
    short: "安全",
    description: "密钥、私钥与敏感信息是否入库",
  },
};

export const DIMENSION_ORDER: DimensionKey[] = [
  "readme",
  "dependencies",
  "startup",
  "cross_platform",
  "security",
];

export const GRADE_META: Record<
  string,
  { label: string; hex: string; text: string; bg: string; border: string }
> = {
  A: {
    label: "优秀",
    hex: "#34D399",
    text: "text-accent",
    bg: "bg-accent/10",
    border: "border-accent/30",
  },
  B: {
    label: "良好",
    hex: "#22D3EE",
    text: "text-accent-2",
    bg: "bg-accent-2/10",
    border: "border-accent-2/30",
  },
  C: {
    label: "需治理",
    hex: "#FBBF24",
    text: "text-medium",
    bg: "bg-medium/10",
    border: "border-medium/30",
  },
  D: {
    label: "风险较高",
    hex: "#FB923C",
    text: "text-high",
    bg: "bg-high/10",
    border: "border-high/30",
  },
  F: {
    label: "阻断",
    hex: "#F87171",
    text: "text-critical",
    bg: "bg-critical/10",
    border: "border-critical/30",
  },
};

export function gradeMeta(grade: string) {
  return GRADE_META[grade] || GRADE_META.F;
}

export function scoreColor(score: number): string {
  if (score >= 90) return "#34D399";
  if (score >= 80) return "#22D3EE";
  if (score >= 70) return "#FBBF24";
  if (score >= 60) return "#FB923C";
  return "#F87171";
}

export function platformLabel(platform: Platform): string {
  return platform === "gitee" ? "Gitee" : "GitHub";
}

export function detectPlatform(url: string): Platform | null {
  const lower = url.toLowerCase();
  if (lower.includes("github.com")) return "github";
  if (lower.includes("gitee.com")) return "gitee";
  return null;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value >= 10_000) return `${(value / 1000).toFixed(1)}k`;
  return String(value);
}

export function truncate(value: string, limit = 120): string {
  if (value.length <= limit) return value;
  return `${value.slice(0, limit - 1)}…`;
}

export function purposeLabel(purpose: string): string {
  const map: Record<string, string> = {
    start: "启动",
    install: "安装",
    build: "构建",
    test: "测试",
    deploy: "部署",
    db: "数据库",
    unknown: "未知",
  };
  return map[purpose] || purpose;
}

export function flagLabel(flag: string): string {
  const map: Record<string, string> = {
    execution_policy_bypass: "绕过执行策略",
    encoded_command: "编码命令",
    download_execute: "下载后执行",
    run_as_admin: "管理员提权",
    wscript_shell: "WScript.Shell",
    hardcoded_path: "硬编码路径",
  };
  return map[flag] || flag;
}

export function sourceLabel(source: string): string {
  const map: Record<string, string> = {
    package_script: "package.json",
    makefile: "Makefile",
    dockerfile: "Dockerfile",
    compose: "Compose",
    procfile: "Procfile",
    pyproject: "pyproject",
    script: "脚本",
    readme: "README",
    other: "其他",
  };
  return map[source] || source;
}

export function confidenceLabel(value: string): string {
  return { high: "高置信", medium: "中置信", low: "低置信" }[value] || value;
}

export function severityCounts(risks: Risk[]): Record<Severity, number> {
  const counts: Record<Severity, number> = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    info: 0,
  };
  for (const risk of risks) counts[risk.severity] += 1;
  return counts;
}

export function riskLocation(risk: Risk): string {
  if (!risk.file) return "仓库级";
  return risk.line ? `${risk.file}:${risk.line}` : risk.file;
}

export function summaryCached(summary: ReportSummary): string {
  return summary.cached ? "缓存" : "新报告";
}

export function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol);
  } catch {
    return false;
  }
}
