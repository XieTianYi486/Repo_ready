import {
  AlertTriangle,
  Check,
  Copy,
  ExternalLink,
  Loader2,
  type LucideIcon,
} from "lucide-react";
import {
  useState,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { cx } from "../lib/format";

export function Panel({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx("panel", className)} {...props}>
      {children}
    </div>
  );
}

export function PageContainer({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8", className)}>
      {children}
    </div>
  );
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "secondary",
  size = "md",
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
}) {
  const variants: Record<ButtonVariant, string> = {
    primary:
      "bg-accent text-[#042f23] hover:bg-[#5ee5b3] border border-accent/80 shadow-[0_0_28px_rgba(52,211,153,0.18)]",
    secondary:
      "bg-surface-2 text-ink hover:bg-[#1b2a47] border border-line",
    ghost:
      "bg-transparent text-muted hover:text-ink hover:bg-surface-2/80 border border-transparent",
    danger:
      "bg-critical/10 text-critical hover:bg-critical/20 border border-critical/30",
  };
  const sizes = {
    sm: "h-8 px-3 text-xs rounded-lg gap-1.5",
    md: "h-10 px-4 text-sm rounded-xl gap-2",
    lg: "h-12 px-5 text-sm rounded-xl gap-2",
  };
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-45",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function Pill({
  children,
  className,
  tone = "neutral",
}: {
  children: ReactNode;
  className?: string;
  tone?: "neutral" | "accent" | "warning" | "danger" | "info";
}) {
  const tones = {
    neutral: "border-line bg-surface-2/70 text-muted",
    accent: "border-accent/25 bg-accent/10 text-accent",
    warning: "border-medium/25 bg-medium/10 text-medium",
    danger: "border-critical/25 bg-critical/10 text-critical",
    info: "border-accent-2/25 bg-accent-2/10 text-accent-2",
  };
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function IconBadge({
  icon: Icon,
  className,
}: {
  icon: LucideIcon;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex h-9 w-9 items-center justify-center rounded-xl border border-line bg-surface-2/80 text-accent-2",
        className,
      )}
    >
      <Icon size={17} aria-hidden="true" />
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <Loader2
      className={cx("h-4 w-4 animate-spin", className)}
      aria-hidden="true"
    />
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton rounded-lg", className)} />;
}

export function CopyButton({
  text,
  label = "复制",
  className,
  iconSize = 13,
}: {
  text: string;
  label?: string;
  className?: string;
  iconSize?: number;
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={cx(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] text-muted transition-colors hover:bg-surface-2 hover:text-ink",
        className,
      )}
      aria-label={copied ? "已复制" : label}
    >
      {copied ? (
        <Check size={iconSize} className="text-accent" aria-hidden="true" />
      ) : (
        <Copy size={iconSize} aria-hidden="true" />
      )}
      <span>{copied ? "已复制" : label}</span>
    </button>
  );
}

export function ExternalAnchor({
  href,
  children,
  className,
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={cx(
        "inline-flex items-center gap-1 text-accent-2 transition-colors hover:text-accent",
        className,
      )}
    >
      {children}
      <ExternalLink size={12} aria-hidden="true" />
    </a>
  );
}

export function ErrorNotice({
  title = "出错了",
  message,
  action,
  className,
}: {
  title?: string;
  message: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "rounded-xl border border-critical/25 bg-critical/8 p-4 text-sm",
        className,
      )}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle
          size={18}
          className="mt-0.5 shrink-0 text-critical"
          aria-hidden="true"
        />
        <div className="min-w-0 space-y-1">
          <p className="font-medium text-critical">{title}</p>
          <p className="break-words text-muted">{message}</p>
          {action ? <div className="pt-2">{action}</div> : null}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-line px-6 py-10 text-center",
        className,
      )}
    >
      <span className="mb-3 inline-flex h-11 w-11 items-center justify-center rounded-full border border-line bg-surface-2 text-muted">
        <Icon size={20} aria-hidden="true" />
      </span>
      <p className="text-sm font-medium text-ink">{title}</p>
      {description ? (
        <p className="mt-1 max-w-md text-xs leading-5 text-muted">{description}</p>
      ) : null}
    </div>
  );
}

export function Divider({ className }: { className?: string }) {
  return <div className={cx("h-px w-full bg-line/70", className)} />;
}

export function Mono({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <code
      className={cx(
        "rounded bg-[#091224] px-1.5 py-0.5 font-mono text-[12px] text-[#c8d6ee]",
        className,
      )}
    >
      {children}
    </code>
  );
}
