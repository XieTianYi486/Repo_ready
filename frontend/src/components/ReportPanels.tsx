import {
  AlertTriangle,
  Check,
  FileText,
  FolderTree,
  KeyRound,
  Monitor,
  Package,
  Play,
  ShieldCheck,
  X,
} from "lucide-react";
import type { ReactNode } from "react";
import {
  SEVERITY_META,
  confidenceLabel,
  cx,
  flagLabel,
  formatNumber,
  purposeLabel,
  sourceLabel,
} from "../lib/format";
import type { Report } from "../lib/types";
import { CopyButton, EmptyState, Panel, Pill } from "./ui";

function DetailHeader({
  title,
  description,
  icon,
  actions,
}: {
  title: string;
  description: string;
  icon: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-line bg-surface-2 text-accent-2">
          {icon}
        </span>
        <div>
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          <p className="mt-0.5 text-[11px] leading-5 text-muted">{description}</p>
        </div>
      </div>
      {actions}
    </div>
  );
}

function sourceUrl(report: Report, path: string, line?: number): string {
  const encoded = path.split("/").map(encodeURIComponent).join("/");
  return `${report.repo.html_url}/blob/${report.commit.sha}/${encoded}${
    line ? `#L${line}` : ""
  }`;
}

function LocationLink({
  report,
  path,
  line,
}: {
  report: Report;
  path: string;
  line?: number;
}) {
  return (
    <a
      href={sourceUrl(report, path, line)}
      target="_blank"
      rel="noreferrer"
      className="font-mono text-[10px] text-accent-2 hover:text-accent"
    >
      {path}
      {line ? `:${line}` : ""}
    </a>
  );
}

function SeverityPill({ severity }: { severity: keyof typeof SEVERITY_META }) {
  const meta = SEVERITY_META[severity];
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px]",
        meta.border,
        meta.bg,
        meta.text,
      )}
    >
      <span
        className="h-1 w-1 rounded-full"
        style={{ background: meta.hex }}
        aria-hidden="true"
      />
      {meta.label}
    </span>
  );
}

const SCOPE_LABELS: Record<string, string> = {
  source: "源码",
  config: "配置",
  script: "脚本",
  docs: "文档",
  test: "测试",
  ci: "CI",
  other: "其他",
};

export function ReadmePanel({ report }: { report: Report }) {
  const section = report.sections.readme;
  return (
    <Panel className="p-5">
      <DetailHeader
        icon={<FileText size={16} aria-hidden="true" />}
        title="README 完整度"
        description="检查安装、使用、配置、架构/API 与许可证等关键章节"
        actions={
          <Pill tone={section.present ? "accent" : "danger"}>
            {section.present ? `${section.score} / 100` : "缺失"}
          </Pill>
        }
      />
      {!section.present ? (
        <EmptyState
          icon={FileText}
          title="未发现根目录 README"
          description="这是接入阻断项：接入者无法从仓库直接了解项目用途、安装与启动方式。"
          className="mt-4"
        />
      ) : (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-muted">
            <span className="font-mono">{section.path}</span>
            <span className="text-faint">·</span>
            <span>{formatNumber(section.chars)} 字符</span>
            <span className="text-faint">·</span>
            <span>{formatNumber(section.lines)} 行</span>
            <span className="text-faint">·</span>
            <span>{section.code_blocks} 个代码块</span>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            {section.sections.map((check) => (
              <div
                key={check.key}
                className={cx(
                  "rounded-lg border px-3 py-2.5",
                  check.present
                    ? "border-accent/20 bg-accent/5"
                    : "border-line bg-[#0a1424]/60",
                )}
              >
                <p className="flex items-center gap-1.5 text-[11px] font-medium text-ink">
                  {check.present ? (
                    <Check size={12} className="text-accent" aria-hidden="true" />
                  ) : (
                    <X size={12} className="text-faint" aria-hidden="true" />
                  )}
                  {check.label}
                </p>
                <p className="mt-1 text-[10px] text-faint">
                  {check.present ? "已覆盖" : "未识别到"}
                </p>
              </div>
            ))}
          </div>
          {section.headings.length ? (
            <div className="mt-4">
              <p className="text-[10px] uppercase tracking-[0.12em] text-faint">
                识别到的标题
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {section.headings.slice(0, 12).map((heading) => (
                  <span
                    key={heading}
                    className="rounded border border-line bg-surface px-2 py-1 text-[10px] text-muted"
                  >
                    {heading}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          {section.placeholders.length ? (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-medium/25 bg-medium/8 px-3 py-2 text-[11px] text-medium">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
              <p>检测到模板占位文本：{section.placeholders.join("、")}</p>
            </div>
          ) : null}
        </>
      )}
    </Panel>
  );
}

export function DependenciesPanel({ report }: { report: Report }) {
  const section = report.sections.dependencies;
  return (
    <Panel className="p-5">
      <DetailHeader
        icon={<Package size={16} aria-hidden="true" />}
        title="依赖清单"
        description="清单、锁文件、解析状态与多生态覆盖"
        actions={<Pill tone={section.has_manifest ? "accent" : "danger"}>{section.score} / 100</Pill>}
      />
      {!section.has_manifest ? (
        <EmptyState
          icon={Package}
          title="未发现依赖清单"
          description="如果仓库包含源码，接入方将无法稳定安装依赖；建议补充 package.json / requirements.txt / go.mod 等标准清单。"
          className="mt-4"
        />
      ) : (
        <>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {section.ecosystems.map((ecosystem) => (
              <Pill key={ecosystem} tone="info">
                {ecosystem}
              </Pill>
            ))}
            <Pill tone={section.lockfiles.length ? "accent" : "warning"}>
              {section.lockfiles.length} 个锁文件
            </Pill>
          </div>
          <div className="mt-4 overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[640px] text-left text-[11px]">
              <thead className="bg-[#0a1424]/80 text-[10px] uppercase tracking-[0.1em] text-faint">
                <tr>
                  <th className="px-3 py-2 font-medium">清单</th>
                  <th className="px-3 py-2 font-medium">生态</th>
                  <th className="px-3 py-2 font-medium">解析</th>
                  <th className="px-3 py-2 font-medium">依赖数</th>
                  <th className="px-3 py-2 font-medium">锁文件</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/70">
                {section.manifests.map((manifest) => (
                  <tr key={manifest.path} className="text-muted">
                    <td className="px-3 py-2.5">
                      <LocationLink report={report} path={manifest.path} />
                      {!manifest.primary ? (
                        <span className="ml-1.5 text-[9px] text-faint">子包</span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2.5">{manifest.ecosystem}</td>
                    <td className="px-3 py-2.5">
                      <span className={manifest.parse_ok ? "text-accent" : "text-critical"}>
                        {manifest.parse_ok ? "✓ 可解析" : "✗ 解析失败"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 font-mono">
                      {manifest.dependency_count}
                      {manifest.dev_dependency_count
                        ? ` (+${manifest.dev_dependency_count} dev)`
                        : ""}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-[10px]">
                      {manifest.lockfile || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {section.manifests.some((manifest) => manifest.issues.length) ? (
            <div className="mt-3 rounded-lg border border-high/20 bg-high/5 px-3 py-2 text-[10px] leading-5 text-high">
              {section.manifests
                .filter((manifest) => manifest.issues.length)
                .map((manifest) => (
                  <p key={manifest.path}>
                    {manifest.path}：{manifest.issues.join("；")}
                  </p>
                ))}
            </div>
          ) : null}
          <p className="mt-3 text-[11px] text-muted">{section.summary}</p>
        </>
      )}
    </Panel>
  );
}

export function StartupPanel({ report }: { report: Report }) {
  const section = report.sections.startup;
  return (
    <Panel className="p-5">
      <DetailHeader
        icon={<Play size={16} aria-hidden="true" />}
        title="启动路径"
        description="脚本、文档命令、容器配置与建议启动方式"
        actions={<Pill tone={section.score >= 70 ? "accent" : "warning"}>{section.score} / 100</Pill>}
      />
      {section.suggested_command ? (
        <div className="mt-4 rounded-xl border border-accent/20 bg-accent/5 p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[10px] uppercase tracking-[0.12em] text-accent/80">
              建议启动命令
            </p>
            <CopyButton text={section.suggested_command} label="复制命令" />
          </div>
          <code className="mt-1.5 block break-all font-mono text-xs text-ink">
            {section.suggested_command}
          </code>
        </div>
      ) : (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-high/25 bg-high/8 px-3 py-2 text-[11px] text-high">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
          <p>未推断出可执行的启动命令。请补充脚本、Makefile、Compose 或 README 说明。</p>
        </div>
      )}

      {section.mismatches.length ? (
        <div className="mt-3 rounded-lg border border-medium/25 bg-medium/8 px-3 py-2 text-[11px] leading-5 text-medium">
          {section.mismatches.map((mismatch) => (
            <p key={mismatch}>· {mismatch}</p>
          ))}
        </div>
      ) : null}

      {section.entries.length ? (
        <div className="mt-4 overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[620px] text-left text-[11px]">
            <thead className="bg-[#0a1424]/80 text-[10px] uppercase tracking-[0.1em] text-faint">
              <tr>
                <th className="px-3 py-2 font-medium">来源</th>
                <th className="px-3 py-2 font-medium">命令 / 目标</th>
                <th className="px-3 py-2 font-medium">核对</th>
                <th className="px-3 py-2 font-medium">说明</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/70">
              {section.entries.map((entry, index) => (
                <tr key={`${entry.source}-${entry.command}-${index}`} className="text-muted">
                  <td className="whitespace-nowrap px-3 py-2.5">
                    {sourceLabel(entry.source)}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-[10px] text-ink">
                    {entry.command}
                  </td>
                  <td className="px-3 py-2.5">
                    {entry.verified ? (
                      <span className="inline-flex items-center gap-1 text-accent">
                        <Check size={11} aria-hidden="true" /> 已核对
                      </span>
                    ) : (
                      <span className="text-faint">待确认</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-[10px]">{entry.detail || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          icon={Play}
          title="未发现启动路径"
          description="没有 package.json scripts、Makefile、Docker、Procfile、启动脚本或 README 命令。"
          className="mt-4"
        />
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-line bg-[#0a1424]/60 p-3">
          <p className="text-[10px] uppercase tracking-[0.12em] text-faint">
            环境变量
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {section.env_vars.length ? (
              section.env_vars.slice(0, 16).map((name) => (
                <span
                  key={name}
                  className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono text-[10px] text-muted"
                >
                  {name}
                </span>
              ))
            ) : (
              <span className="text-[11px] text-faint">未检测到环境变量引用</span>
            )}
          </div>
          <p className="mt-2 text-[10px] text-muted">
            .env.example：{section.env_example ? "已提供" : "未提供"}
          </p>
        </div>
        <div className="rounded-lg border border-line bg-[#0a1424]/60 p-3">
          <p className="text-[10px] uppercase tracking-[0.12em] text-faint">
            容器 / 进程
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Pill tone={section.has_docker ? "accent" : "neutral"}>
              Dockerfile {section.has_docker ? "有" : "无"}
            </Pill>
            <Pill tone={section.has_compose ? "accent" : "neutral"}>
              Compose {section.has_compose ? "有" : "无"}
            </Pill>
            <Pill tone={section.has_procfile ? "accent" : "neutral"}>
              Procfile {section.has_procfile ? "有" : "无"}
            </Pill>
            <Pill tone={section.has_makefile ? "accent" : "neutral"}>
              Makefile {section.has_makefile ? "有" : "无"}
            </Pill>
          </div>
        </div>
      </div>
    </Panel>
  );
}

export function WindowsPanel({ report }: { report: Report }) {
  const section = report.sections.windows;
  return (
    <Panel className="p-5">
      <DetailHeader
        icon={<Monitor size={16} aria-hidden="true" />}
        title="Windows 专用脚本"
        description=".bat / .cmd / .ps1 / .vbs 盘点与高风险执行模式"
        actions={<Pill tone={section.count ? "warning" : "accent"}>{section.count} 个</Pill>}
      />
      {section.only_windows_start ? (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-high/25 bg-high/8 px-3 py-2 text-[11px] text-high">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
          <p>启动方式仅限 Windows，macOS / Linux / CI 环境可能无法直接运行。</p>
        </div>
      ) : null}
      {section.count === 0 ? (
        <EmptyState
          icon={Monitor}
          title="未发现 Windows 专用脚本"
          description="跨平台风险较低；如果仓库只支持 Windows，请确认这是否符合接入目标环境。"
          className="mt-4"
        />
      ) : (
        <div className="mt-4 overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[680px] text-left text-[11px]">
            <thead className="bg-[#0a1424]/80 text-[10px] uppercase tracking-[0.1em] text-faint">
              <tr>
                <th className="px-3 py-2 font-medium">文件</th>
                <th className="px-3 py-2 font-medium">用途</th>
                <th className="px-3 py-2 font-medium">README 引用</th>
                <th className="px-3 py-2 font-medium">风险标记</th>
                <th className="px-3 py-2 font-medium">严重度</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/70">
              {section.files.map((file) => (
                <tr key={file.path} className="text-muted">
                  <td className="max-w-[240px] px-3 py-2.5">
                    <LocationLink report={report} path={file.path} />
                  </td>
                  <td className="px-3 py-2.5">{purposeLabel(file.purpose)}</td>
                  <td className="px-3 py-2.5">
                    {file.referenced ? (
                      <span className="text-accent">是</span>
                    ) : (
                      <span className="text-faint">否</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    {file.flags.length ? (
                      <div className="flex flex-wrap gap-1">
                        {file.flags.map((flag) => (
                          <span
                            key={flag}
                            className="rounded border border-line bg-surface px-1.5 py-0.5 text-[9px] text-muted"
                          >
                            {flagLabel(flag)}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-faint">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <SeverityPill severity={file.severity} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

export function PathsPanel({ report }: { report: Report }) {
  const section = report.sections.paths;
  return (
    <Panel className="p-5">
      <DetailHeader
        icon={<FolderTree size={16} aria-hidden="true" />}
        title="硬编码路径"
        description="Windows 盘符、macOS/Linux 用户目录、UNC 与部署绝对路径"
        actions={
          <Pill tone={section.counts_by_severity.high ? "danger" : section.findings.length ? "warning" : "accent"}>
            {section.findings.length} 处
          </Pill>
        }
      />
      <div className="mt-3 flex flex-wrap gap-1.5">
        {Object.entries(section.counts_by_severity).map(([severity, count]) => (
          <span key={severity} className="text-[10px] text-muted">
            {SEVERITY_META[severity as keyof typeof SEVERITY_META]?.label || severity}{" "}
            {count}
          </span>
        ))}
        <span className="text-[10px] text-faint">· 扣分 {section.penalty}</span>
      </div>
      {section.findings.length === 0 ? (
        <EmptyState
          icon={FolderTree}
          title="未发现硬编码绝对路径"
          description="源码、配置与脚本中未命中盘符、用户目录、UNC 或部署绝对路径规则。"
          className="mt-4"
        />
      ) : (
        <div className="mt-4 max-h-[520px] overflow-auto rounded-lg border border-line">
          <table className="w-full min-w-[760px] text-left text-[11px]">
            <thead className="sticky top-0 z-10 bg-[#0a1424] text-[10px] uppercase tracking-[0.1em] text-faint">
              <tr>
                <th className="px-3 py-2 font-medium">严重度</th>
                <th className="px-3 py-2 font-medium">规则</th>
                <th className="px-3 py-2 font-medium">位置</th>
                <th className="px-3 py-2 font-medium">场景</th>
                <th className="px-3 py-2 font-medium">证据（已脱敏）</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/70">
              {section.findings.map((finding, index) => (
                <tr
                  key={`${finding.rule_id}-${finding.path}-${finding.line}-${index}`}
                  className="text-muted"
                >
                  <td className="px-3 py-2.5">
                    <SeverityPill severity={finding.severity} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[10px]">
                    {finding.rule_id.replace("PATH-", "")}
                  </td>
                  <td className="max-w-[220px] px-3 py-2.5">
                    <LocationLink
                      report={report}
                      path={finding.path}
                      line={finding.line}
                    />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[10px]">
                    {SCOPE_LABELS[finding.scope] || finding.scope}
                  </td>
                  <td className="max-w-[320px] px-3 py-2.5">
                    <code className="break-all font-mono text-[10px] text-[#c8d6ee]">
                      {finding.snippet}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

export function SecretsPanel({ report }: { report: Report }) {
  const section = report.sections.secrets;
  return (
    <Panel className="p-5">
      <DetailHeader
        icon={<KeyRound size={16} aria-hidden="true" />}
        title="密钥与敏感信息"
        description="所有敏感值均已脱敏；不会在页面、导出或 AI 请求中出现明文"
        actions={
          <Pill
            tone={
              section.counts_by_severity.critical
                ? "danger"
                : section.counts_by_severity.high
                  ? "warning"
                  : "accent"
            }
          >
            {section.findings.length} 处
          </Pill>
        }
      />
      <div className="mt-3 flex flex-wrap gap-2">
        {(Object.keys(SEVERITY_META) as Array<keyof typeof SEVERITY_META>).map(
          (severity) =>
            section.counts_by_severity[severity] ? (
              <SeverityPill
                key={severity}
                severity={severity}
              />
            ) : null,
        )}
        <Pill tone={section.gitignore_env ? "accent" : "warning"}>
          .gitignore {section.gitignore_env ? "已覆盖 .env" : "未覆盖 .env"}
        </Pill>
      </div>
      {section.env_files.length ? (
        <div className="mt-3 rounded-lg border border-critical/25 bg-critical/8 px-3 py-2 text-[11px] text-critical">
          <p className="font-medium">发现已提交的 .env 文件</p>
          <p className="mt-1 break-all font-mono text-[10px] text-critical/90">
            {section.env_files.join(" · ")}
          </p>
        </div>
      ) : null}
      {section.findings.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title="未发现密钥或敏感信息"
          description="高置信 Token、私钥、Bearer、.env 入库与泛化凭据规则均未命中。"
          className="mt-4"
        />
      ) : (
        <div className="mt-4 max-h-[480px] overflow-auto rounded-lg border border-line">
          <table className="w-full min-w-[720px] text-left text-[11px]">
            <thead className="sticky top-0 z-10 bg-[#0a1424] text-[10px] uppercase tracking-[0.1em] text-faint">
              <tr>
                <th className="px-3 py-2 font-medium">严重度</th>
                <th className="px-3 py-2 font-medium">类型</th>
                <th className="px-3 py-2 font-medium">位置</th>
                <th className="px-3 py-2 font-medium">脱敏值</th>
                <th className="px-3 py-2 font-medium">置信度</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/70">
              {section.findings.map((finding, index) => (
                <tr
                  key={`${finding.rule_id}-${finding.path}-${finding.line}-${index}`}
                  className="text-muted"
                >
                  <td className="px-3 py-2.5">
                    <SeverityPill severity={finding.severity} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[10px]">
                    {finding.kind}
                  </td>
                  <td className="max-w-[240px] px-3 py-2.5">
                    <LocationLink
                      report={report}
                      path={finding.path}
                      line={finding.line}
                    />
                  </td>
                  <td className="px-3 py-2.5 font-mono text-[10px] text-[#c8d6ee]">
                    {finding.masked}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[10px]">
                    {confidenceLabel(finding.confidence)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 flex items-start gap-1.5 text-[10px] leading-5 text-faint">
        <KeyRound size={11} className="mt-0.5 shrink-0" aria-hidden="true" />
        RepoReady 只做静态文本匹配；命中不代表凭据一定有效，但建议按“已泄露”处理并立即轮换。
      </p>
    </Panel>
  );
}
