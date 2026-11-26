import {
  ArrowRight,
  Bot,
  Clock,
  FileText,
  FolderTree,
  GitBranch,
  GitFork,
  KeyRound,
  Lock,
  Monitor,
  Package,
  Play,
  ShieldCheck,
  Sparkles,
  Star,
  Terminal,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError, errorMessage } from "../lib/api";
import {
  DIMENSION_META,
  formatDate,
  gradeMeta,
  platformLabel,
} from "../lib/format";
import type { ExampleRepo, Health, ReportSummary } from "../lib/types";
import {
  Button,
  EmptyState,
  ErrorNotice,
  IconBadge,
  PageContainer,
  Panel,
  Pill,
  Spinner,
} from "../components/ui";

const FEATURES = [
  {
    icon: FileText,
    title: "README 完整度",
    desc: "安装、使用、配置、API、许可证章节与代码示例",
  },
  {
    icon: Package,
    title: "依赖清单",
    desc: "识别 15+ 生态清单与锁文件，检查可解析性",
  },
  {
    icon: Play,
    title: "启动脚本",
    desc: "package scripts、Makefile、Docker、README 命令交叉核对",
  },
  {
    icon: Monitor,
    title: "Windows 专用脚本",
    desc: "盘点 .bat/.cmd/.ps1/.vbs 与高风险执行模式",
  },
  {
    icon: FolderTree,
    title: "硬编码路径",
    desc: "C:\\、/Users/、/home/、UNC 与部署绝对路径",
  },
  {
    icon: KeyRound,
    title: "密钥与敏感信息",
    desc: "sk-、AKID、AKIA、Bearer、私钥、.env 入库，全量脱敏",
  },
];

function PlatformIcon({ platform }: { platform: string }) {
  return platform === "gitee" ? (
    <GitBranch size={16} aria-hidden="true" />
  ) : (
    <GitFork size={16} aria-hidden="true" />
  );
}

export function HomePage() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [examples, setExamples] = useState<ExampleRepo[]>([]);
  const [recent, setRecent] = useState<ReportSummary[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.health(), api.examples(), api.recent(6)])
      .then(([h, e, r]) => {
        if (cancelled) return;
        setHealth(h);
        setExamples(e);
        setRecent(r);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const detectedPlatform = useMemo(() => {
    if (/gitee\.com/i.test(url)) return "gitee";
    if (/github\.com/i.test(url)) return "github";
    return null;
  }, [url]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const value = url.trim();
    if (!value) {
      setError("请先粘贴一个公开仓库链接。");
      return;
    }
    if (!/github\.com|gitee\.com/i.test(value)) {
      setError("目前仅支持 github.com 与 gitee.com 的公开仓库。");
      return;
    }
    setSubmitting(true);
    try {
      const job = await api.startScan(value);
      navigate(`/scan/${job.job_id}`);
    } catch (err) {
      if (err instanceof ApiError && err.code === "RATE_LIMITED") {
        setError(
          `${err.message}${err.retryAfter ? `（约 ${err.retryAfter}s 后重试）` : ""}`,
        );
      } else {
        setError(errorMessage(err));
      }
      setSubmitting(false);
    }
  }

  return (
    <div className="pb-20">
      <PageContainer className="pt-12 lg:pt-20">
        <section className="hero-glow mx-auto max-w-4xl text-center">
          <Pill tone="accent" className="mb-5">
            <Sparkles size={12} aria-hidden="true" />
            Git 仓库接入体检 · GitHub / Gitee
          </Pill>
          <h1 className="text-balance text-4xl font-semibold tracking-tight text-ink sm:text-5xl lg:text-[56px] lg:leading-[1.08]">
            上线前，先给仓库做一次
            <span className="text-gradient"> 接入体检</span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-pretty text-sm leading-7 text-muted sm:text-base">
            粘贴公开仓库链接，自动检查 README、依赖、启动脚本、Windows 专用脚本、
            硬编码路径与敏感信息，给出可解释的接入就绪度评分与风险清单。
          </p>

          <Panel className="mx-auto mt-8 max-w-3xl p-2.5 text-left shadow-[0_24px_80px_rgba(0,0,0,0.34)]">
            <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
              <div className="relative flex-1">
                <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted">
                  {detectedPlatform ? (
                    <PlatformIcon platform={detectedPlatform} />
                  ) : (
                    <GitBranch size={16} aria-hidden="true" />
                  )}
                </span>
                <input
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://github.com/owner/repo 或 https://gitee.com/owner/repo"
                  className="h-12 w-full rounded-xl border border-line bg-[#0a1424] pl-10 pr-4 font-mono text-[13px] text-ink outline-none transition-colors placeholder:font-sans placeholder:text-faint focus:border-accent/50 focus:ring-2 focus:ring-accent/15"
                  aria-label="公开 Git 仓库链接"
                  spellCheck={false}
                  autoComplete="off"
                />
                {detectedPlatform ? (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full border border-line bg-surface px-2 py-1 text-[10px] font-medium text-muted">
                    {platformLabel(detectedPlatform as "github" | "gitee")}
                  </span>
                ) : null}
              </div>
              <Button
                type="submit"
                variant="primary"
                size="lg"
                disabled={submitting}
                className="shrink-0 px-6"
              >
                {submitting ? (
                  <Spinner />
                ) : (
                  <ShieldCheck size={17} aria-hidden="true" />
                )}
                {submitting ? "正在创建体检…" : "开始体检"}
                {!submitting ? <ArrowRight size={15} aria-hidden="true" /> : null}
              </Button>
            </form>
          </Panel>

          {error ? (
            <ErrorNotice
              title="暂时无法开始体检"
              message={error}
              className="mx-auto mt-4 max-w-3xl text-left"
            />
          ) : null}

          <div className="mx-auto mt-5 flex max-w-3xl flex-wrap items-center justify-center gap-2">
            <span className="mr-1 text-[11px] text-faint">试试示例：</span>
            {examples.map((example) => (
              <button
                key={example.url}
                type="button"
                onClick={() => setUrl(example.url)}
                className="group inline-flex items-center gap-1.5 rounded-full border border-line bg-surface/60 px-3 py-1.5 text-[11px] text-muted transition-colors hover:border-accent/30 hover:text-ink"
                title={example.highlight}
              >
                <PlatformIcon platform={example.platform} />
                {example.label}
                <span className="hidden text-faint group-hover:text-muted sm:inline">
                  · {example.highlight.split("：")[0]}
                </span>
              </button>
            ))}
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-[11px] text-faint">
            <span className="inline-flex items-center gap-1.5">
              <Lock size={12} aria-hidden="true" />
              只读取公开仓库，不执行代码
            </span>
            <span className="inline-flex items-center gap-1.5">
              <KeyRound size={12} aria-hidden="true" />
              密钥发现自动脱敏
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Terminal size={12} aria-hidden="true" />
              支持 GitHub Token / Gitee Token 提额
            </span>
          </div>
        </section>

        <section className="mt-16 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <Panel
              key={feature.title}
              className="group p-4 transition-colors hover:border-line/120 hover:bg-surface-2/60"
            >
              <div className="flex items-start gap-3">
                <IconBadge icon={feature.icon} />
                <div>
                  <h2 className="text-sm font-medium text-ink">{feature.title}</h2>
                  <p className="mt-1 text-xs leading-5 text-muted">{feature.desc}</p>
                </div>
              </div>
            </Panel>
          ))}
        </section>

        <section className="mt-14 grid gap-4 lg:grid-cols-[1.45fr_0.9fr]">
          <Panel className="p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <SectionTitle
                  eyebrow="Recent"
                  title="最近体检"
                  description="报告按仓库与 commit 缓存，可随时回访"
                />
              </div>
              <Clock size={18} className="text-muted" aria-hidden="true" />
            </div>
            <div className="mt-5 space-y-2">
              {loading ? (
                <>
                  <div className="skeleton h-16 rounded-xl" />
                  <div className="skeleton h-16 rounded-xl" />
                </>
              ) : recent.length === 0 ? (
                <EmptyState
                  icon={ShieldCheck}
                  title="还没有体检记录"
                  description="在上方粘贴一个公开仓库链接，第一份报告大约 10–30 秒生成。"
                />
              ) : (
                recent.map((item) => {
                  const meta = gradeMeta(item.grade);
                  return (
                    <Link
                      key={item.id}
                      to={`/report/${item.id}`}
                      className="group flex items-center justify-between gap-4 rounded-xl border border-transparent px-3 py-3 transition-colors hover:border-line hover:bg-surface-2/60"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-line bg-surface text-muted">
                            <PlatformIcon platform={item.platform} />
                          </span>
                          <span className="truncate text-sm font-medium text-ink">
                            {item.full_name}
                          </span>
                          <span className="hidden rounded border border-line px-1.5 py-0.5 font-mono text-[10px] text-muted sm:inline">
                            {item.commit_short_sha}
                          </span>
                        </div>
                        <p className="mt-1 flex items-center gap-3 text-[11px] text-faint">
                          <span>{formatDate(item.analyzed_at)}</span>
                          <span className="inline-flex items-center gap-1">
                            <GitBranch size={11} aria-hidden="true" />
                            {item.branch}
                          </span>
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-3">
                        <span
                          className="rounded-full px-2 py-1 text-[10px] font-medium"
                          style={{ color: meta.hex, background: `${meta.hex}14` }}
                        >
                          {item.grade} · {meta.label}
                        </span>
                        <span className="font-mono text-lg font-semibold" style={{ color: meta.hex }}>
                          {item.total}
                        </span>
                        <ArrowRight
                          size={15}
                          className="text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-accent"
                          aria-hidden="true"
                        />
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
          </Panel>

          <div className="space-y-4">
            <Panel className="p-5">
              <SectionTitle
                eyebrow="Scoring"
                title="五维接入就绪度"
                description="确定性规则评分，AI 只给建议、不改分"
              />
              <div className="mt-4 space-y-3">
                {(
                  [
                    ["readme", 20],
                    ["dependencies", 15],
                    ["startup", 20],
                    ["cross_platform", 15],
                    ["security", 30],
                  ] as const
                ).map(([key, weight]) => (
                  <div key={key} className="flex items-center justify-between gap-3">
                    <span className="text-xs text-muted">
                      {DIMENSION_META[key].label}
                    </span>
                    <span className="font-mono text-[11px] text-faint">
                      {weight}%
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-4 rounded-lg border border-line bg-[#0a1424]/70 px-3 py-2 text-[11px] leading-5 text-muted">
                critical 密钥一票封顶 49 分；high 封顶 69 分。评分公式与规则版本在每份报告中可查。
              </div>
            </Panel>

            <Panel className="p-5">
              <SectionTitle
                eyebrow="Runtime"
                title="运行配置"
                description="没有 Token / AI Key 也能完成核心体检"
              />
              <div className="mt-4 space-y-2.5 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <span className="inline-flex items-center gap-2 text-muted">
                    <Bot size={14} aria-hidden="true" />
                    AI 建议
                  </span>
                  {health?.ai.enabled ? (
                    <Pill tone="accent">
                      {health.ai.provider} · {health.ai.model}
                    </Pill>
                  ) : (
                    <Pill tone="neutral">未配置（可选）</Pill>
                  )}
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="inline-flex items-center gap-2 text-muted">
                    <GitFork size={14} aria-hidden="true" />
                    GitHub Token
                  </span>
                  <Pill tone={health?.tokens.github ? "accent" : "neutral"}>
                    {health?.tokens.github ? "已配置" : "未配置"}
                  </Pill>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="inline-flex items-center gap-2 text-muted">
                    <GitBranch size={14} aria-hidden="true" />
                    Gitee Token
                  </span>
                  <Pill tone={health?.tokens.gitee ? "accent" : "neutral"}>
                    {health?.tokens.gitee ? "已配置" : "未配置"}
                  </Pill>
                </div>
              </div>
            </Panel>
          </div>
        </section>

        <section className="mt-14">
          <Panel className="flex flex-col items-start justify-between gap-5 p-6 sm:flex-row sm:items-center">
            <div>
              <p className="text-sm font-medium text-ink">
                不只是评分，还是一份可执行的整改清单
              </p>
              <p className="mt-1 text-xs leading-5 text-muted">
                每条风险包含文件、行号、脱敏证据、修复建议与源码链接；支持导出 JSON / Markdown。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Pill tone="info">
                <Star size={11} aria-hidden="true" />
                可解释评分
              </Pill>
              <Pill tone="info">
                <GitFork size={11} aria-hidden="true" />
                双平台
              </Pill>
              <Pill tone="info">
                <Bot size={11} aria-hidden="true" />
                AI 建议
              </Pill>
            </div>
          </Panel>
        </section>
      </PageContainer>
    </div>
  );
}

function SectionTitle({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description?: string;
}) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent/80">
        {eyebrow}
      </p>
      <h2 className="mt-1 text-base font-semibold text-ink">{title}</h2>
      {description ? (
        <p className="mt-1 text-[11px] leading-5 text-muted">{description}</p>
      ) : null}
    </div>
  );
}
