import { BookOpen, ShieldCheck } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { cx } from "../lib/format";
import { PageContainer, Pill } from "./ui";

function Logo() {
  return (
    <span className="relative inline-flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl border border-accent/25 bg-[linear-gradient(145deg,#12283a,#0c182b)] shadow-[0_0_24px_rgba(52,211,153,0.12)]">
      <span className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(52,211,153,0.26),transparent_58%)]" />
      <ShieldCheck size={21} className="relative text-accent" aria-hidden="true" />
    </span>
  );
}

export function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-line/80 bg-page/80 backdrop-blur-xl">
        <PageContainer className="flex h-16 items-center justify-between gap-4">
          <Link to="/" className="group flex items-center gap-3">
            <Logo />
            <span className="min-w-0">
              <span className="flex items-baseline gap-2">
                <span className="text-[17px] font-semibold tracking-tight text-ink">
                  RepoReady
                </span>
                <span className="hidden rounded border border-line bg-surface/70 px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-muted sm:inline">
                  v1.0
                </span>
              </span>
              <span className="block text-[11px] tracking-wide text-muted">
                Git 仓库接入体检
              </span>
            </span>
          </Link>

          <div className="flex items-center gap-2 sm:gap-3">
            <div className="hidden items-center gap-1.5 md:flex">
              <Pill tone="neutral">GitHub</Pill>
              <Pill tone="neutral">Gitee</Pill>
              <Pill tone="accent">
                <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                只读扫描
              </Pill>
            </div>
            <nav className="flex items-center gap-1">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  cx(
                    "rounded-lg px-3 py-2 text-xs font-medium transition-colors",
                    isActive
                      ? "bg-surface-2 text-ink"
                      : "text-muted hover:bg-surface-2/70 hover:text-ink",
                  )
                }
              >
                首页
              </NavLink>
              <a
                href="/api/docs"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium text-muted transition-colors hover:bg-surface-2/70 hover:text-ink"
              >
                <BookOpen size={14} aria-hidden="true" />
                API 文档
              </a>
            </nav>
          </div>
        </PageContainer>
      </header>

      <main className="min-h-[calc(100vh-4rem)] flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-line/70">
        <PageContainer className="flex flex-col gap-3 py-6 text-[11px] text-faint sm:flex-row sm:items-center sm:justify-between">
          <p className="leading-5">
            RepoReady · 静态扫描，不执行仓库代码 · 密钥结果自动脱敏 · 评分仅供参考
          </p>
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>FastAPI + React</span>
            <span className="hidden h-1 w-1 rounded-full bg-line sm:inline-block" />
            <a href="/api/docs" className="hover:text-muted" target="_blank" rel="noreferrer">
              OpenAPI
            </a>
            <span className="hidden h-1 w-1 rounded-full bg-line sm:inline-block" />
            <span>MIT License</span>
          </p>
        </PageContainer>
      </footer>
    </div>
  );
}
