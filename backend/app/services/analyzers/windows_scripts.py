from __future__ import annotations

import re
from pathlib import PurePosixPath

from ...models import WindowsScriptInfo, WindowsSection
from .common import build_risk
from .context import AnalyzerContext, AnalyzerOutput

WINDOWS_EXTENSIONS = {".bat", ".cmd", ".ps1", ".vbs"}
PURPOSE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("start", ("start", "run", "launch", "serve", "dev", "启动", "运行")),
    ("install", ("install", "setup", "init", "bootstrap", "env", "安装", "初始化")),
    ("build", ("build", "compile", "package", "构建", "编译")),
    ("test", ("test", "测试")),
    ("deploy", ("deploy", "publish", "release", "upload", "部署", "发布")),
    ("db", ("sql", "migrate", "database", "数据库")),
)
RISKY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("execution_policy_bypass", re.compile(r"(?i)-ExecutionPolicy\s+Bypass")),
    ("encoded_command", re.compile(r"(?i)-EncodedCommand")),
    (
        "download_execute",
        re.compile(
            r"(?is)(?:invoke-webrequest|iwr|curl)[^\n]{0,240}(?:\|\s*(?:iex|invoke-expression)|powershell)"
        ),
    ),
    ("run_as_admin", re.compile(r"(?i)(?:-Verb\s+RunAs|\brunas\b)")),
    ("wscript_shell", re.compile(r"(?i)WScript\.Shell")),
    ("hardcoded_path", re.compile(r"(?<![\w])[A-Za-z]:[\\/][^\s\"'<>|*?\r\n]{2,120}")),
)


def _purpose(path: str, text: str) -> str:
    filename = path.lower()
    for purpose, keywords in PURPOSE_KEYWORDS:
        if any(keyword in filename for keyword in keywords):
            return purpose
    content = "\n".join(text.splitlines()[:80]).lower()
    for purpose, keywords in PURPOSE_KEYWORDS:
        if any(keyword in content for keyword in keywords):
            return purpose
    return "unknown"


def _flags(text: str) -> list[str]:
    flags = []
    for name, pattern in RISKY_PATTERNS:
        if pattern.search(text):
            flags.append(name)
    return flags


def analyze_windows(ctx: AnalyzerContext) -> AnalyzerOutput:
    files: list[WindowsScriptInfo] = []
    readme_text = (ctx.readme_text or "").lower()
    for entry in ctx.index.entries:
        if entry.ext not in WINDOWS_EXTENSIONS:
            continue
        text = ctx.index.text_for(entry) or ""
        flags = _flags(text)
        severity = "info"
        if any(
            flag in flags
            for flag in (
                "execution_policy_bypass",
                "encoded_command",
                "download_execute",
                "run_as_admin",
            )
        ):
            severity = "medium"
        elif "wscript_shell" in flags or "hardcoded_path" in flags:
            severity = "low"
        basename = PurePosixPath(entry.rel_path).name.lower()
        referenced = basename in readme_text or entry.rel_path.lower() in readme_text
        files.append(
            WindowsScriptInfo(
                path=entry.rel_path,
                extension=entry.ext,
                size=entry.size,
                purpose=_purpose(entry.rel_path, text),
                referenced=referenced,
                flags=flags,
                severity=severity,  # type: ignore[arg-type]
            )
        )
    files.sort(key=lambda item: item.path.lower())

    start_scripts = [item for item in files if item.purpose == "start"]
    cross_platform_start = False
    if ctx.startup:
        cross_platform_start = any(
            entry.source in {"package_script", "makefile", "compose", "procfile", "pyproject"}
            and not entry.command.endswith("run build")
            for entry in ctx.startup.entries
        ) or any(
            entry.source == "dockerfile" for entry in ctx.startup.entries
        ) or any(
            entry.source == "script"
            and (entry.path or "").lower().endswith(".sh")
            for entry in ctx.startup.entries
        )
        if not cross_platform_start:
            cross_platform_start = any(
                not re.search(
                    r"(?:^|\s)(?:\S+\.(?:bat|cmd|ps1|vbs))(?:\s|$)",
                    command,
                    re.IGNORECASE,
                )
                for command in ctx.startup.documented_commands
            )
    if not cross_platform_start:
        names = {entry.rel_path.lower() for entry in ctx.index.entries}
        cross_platform_start = any(
            name.endswith((".sh", "makefile", "dockerfile", "compose.yml", "compose.yaml"))
            for name in names
        )
    only_windows_start = bool(start_scripts) and not cross_platform_start

    risky_scripts = [
        item for item in files if item.severity in {"medium", "low"}
    ]
    penalty = min(15, len(files) * 3)
    if only_windows_start:
        penalty += 15
    penalty += min(20, len(risky_scripts) * 10)
    penalty = min(50, penalty)

    risks = []
    if only_windows_start:
        first = start_scripts[0]
        risks.append(
            build_risk(
                rule_id="WIN-ONLY-START",
                dimension="cross_platform",
                category="platform",
                severity="medium",
                title="仅提供 Windows 启动脚本",
                description="仓库只有 .bat/.cmd/.ps1/.vbs 启动方式，macOS/Linux 或 CI 环境无法直接运行。",
                recommendation="提供 .sh / Makefile / Docker 等跨平台启动方式，或把核心逻辑移到跨平台脚本。",
                path=first.path,
                evidence=first.path,
                source_url=ctx.source_url(first.path, 1),
                confidence="high",
                blocking=False,
            )
        )
    unsafe = [
        item
        for item in files
        if any(
            flag in item.flags
            for flag in (
                "execution_policy_bypass",
                "encoded_command",
                "download_execute",
                "run_as_admin",
            )
        )
    ]
    if unsafe:
        first = unsafe[0]
        flag_text = ", ".join(sorted({flag for item in unsafe for flag in item.flags}))
        risks.append(
            build_risk(
                rule_id="WIN-RISKY-SCRIPT",
                dimension="cross_platform",
                category="platform",
                severity="medium",
                title="Windows 脚本包含高权限/下载执行模式",
                description="脚本使用执行策略绕过、编码命令、管理员提权或下载后执行，接入前应人工审查。",
                recommendation="审查并最小化脚本权限；移除下载执行与执行策略绕过，补充校验与来源说明。",
                path=first.path,
                evidence=flag_text,
                occurrences=len(unsafe),
                source_url=ctx.source_url(first.path, 1),
                confidence="high",
                blocking=False,
            )
        )

    reasons = []
    if files:
        reasons.append(f"发现 {len(files)} 个 Windows 专用脚本")
        reasons.append(f"跨平台脚本扣分：-{penalty}")
    else:
        reasons.append("未发现 Windows 专用脚本（不扣分）")
    if only_windows_start:
        reasons.append("启动方式仅 Windows 可用（−15）")
    summary = (
        f"发现 {len(files)} 个 Windows 专用脚本"
        + ("，且启动方式仅限 Windows。" if only_windows_start else "。")
        if files
        else "未发现 .bat/.cmd/.ps1/.vbs 脚本。"
    )
    section = WindowsSection(
        files=files,
        count=len(files),
        only_windows_start=only_windows_start,
        penalty=penalty,
        summary=summary,
    )
    return AnalyzerOutput(
        section=section,
        risks=risks,
        score=max(0, 100 - penalty),
        reasons=reasons,
    )
