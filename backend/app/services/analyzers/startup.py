from __future__ import annotations

import json
import re
import tomllib
from pathlib import PurePosixPath

from ...models import StartupEntry, StartupSection
from .common import build_risk, file_scope
from .context import AnalyzerContext, AnalyzerOutput

RUNNER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?im)^\s*(?:[$>]\s*)?((?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:start|dev|serve|preview)[^\n]*)"
    ),
    re.compile(
        r"(?im)^\s*(?:[$>]\s*)?((?:python3?|py)\s+[-\w./\\]+\.py(?:\s+[^\n]*)?)"
    ),
    re.compile(
        r"(?im)^\s*(?:[$>]\s*)?((?:uvicorn|gunicorn|flask\s+run|django-admin\s+runserver|"
        r"python3?\s+-m\s+(?:uvicorn|flask|http\.server))[^\n]*)"
    ),
    re.compile(
        r"(?im)^\s*(?:[$>]\s*)?((?:go\s+run|cargo\s+run|mvn\s+(?:spring-boot:run|exec:java)|"
        r"\.?[/\\]?gradlew?\s+bootRun|dotnet\s+run|php\s+artisan\s+serve|"
        r"bundle\s+exec\s+rails\s+server|docker(?:\s+compose|[-\s]compose)\s+up)[^\n]*)"
    ),
)
INLINE_COMMAND_RE = re.compile(r"`([^`\n]{2,120})`")
ENV_ASSIGNMENT_RE = re.compile(
    r"(?m)^\s*([A-Z][A-Z0-9_]{2,})\s*="
)
ENV_CODE_PATTERNS = (
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]{2,})"),
    re.compile(r"process\.env\[['\"]([A-Z][A-Z0-9_]{2,})['\"]\]"),
    re.compile(r"os\.environ\.get\(['\"]([A-Z][A-Z0-9_]{2,})['\"]"),
    re.compile(r"os\.environ\[['\"]([A-Z][A-Z0-9_]{2,})['\"]\]"),
    re.compile(r"os\.getenv\(['\"]([A-Z][A-Z0-9_]{2,})['\"]"),
)
BUILD_COMMAND_RE = re.compile(
    r"(?im)^\s*(?:[$>]\s*)?(npm\s+run\s+build|yarn\s+build|pnpm\s+build|make\s+build|"
    r"cargo\s+build|go\s+build|mvn\s+(?:package|install)|gradlew?\s+build|dotnet\s+build)\b"
)


def _root_text(ctx: AnalyzerContext, name: str) -> str | None:
    entry = ctx.index.find_root(name)
    return ctx.index.text_for(entry) if entry else None


def _package_manager(ctx: AnalyzerContext) -> str:
    names = {entry.rel_path.lower() for entry in ctx.index.entries}
    if any(name.endswith("pnpm-lock.yaml") for name in names):
        return "pnpm"
    if any(name.endswith("yarn.lock") for name in names):
        return "yarn"
    if any(name.endswith("bun.lockb") for name in names):
        return "bun"
    return "npm"


def _extract_readme_commands(text: str | None) -> list[str]:
    if not text:
        return []
    commands: list[str] = []
    seen: set[str] = set()
    for pattern in RUNNER_PATTERNS:
        for match in pattern.finditer(text):
            command = match.group(1).strip().rstrip("`").strip()
            command = re.sub(r"\s+", " ", command)
            if command and command.lower() not in seen:
                commands.append(command[:180])
                seen.add(command.lower())
    for match in INLINE_COMMAND_RE.finditer(text):
        candidate = match.group(1).strip()
        if any(pattern.search(candidate) for pattern in RUNNER_PATTERNS):
            if candidate.lower() not in seen:
                commands.append(candidate[:180])
                seen.add(candidate.lower())
    return commands[:10]


def _script_start_entries(ctx: AnalyzerContext) -> list[StartupEntry]:
    entries: list[StartupEntry] = []
    readme_text = (ctx.readme_text or "").lower()
    for entry in ctx.index.entries:
        path = entry.rel_path.lower()
        if entry.ext not in {".sh", ".bat", ".cmd", ".ps1"}:
            continue
        if path.count("/") > 1:
            continue
        name = PurePosixPath(path).name
        if any(
            word in name
            for word in ("install", "setup", "build", "test", "deploy", "migrate")
        ):
            continue
        text = ctx.index.text_for(entry) or ""
        start_like = any(
            word in name for word in ("start", "run", "serve", "dev", "launch")
        ) or any(
            token in text.lower()
            for token in (
                "java -jar",
                "npm run",
                "npm start",
                "node ",
                "python ",
                "uvicorn",
                "gunicorn",
                "mvn ",
                "gradlew",
                "dotnet run",
                "go run",
                "cargo run",
                "start)",
            )
        )
        if not start_like:
            continue
        if entry.ext == ".sh":
            command = f"./{entry.rel_path}"
        elif entry.ext in {".bat", ".cmd"}:
            command = entry.rel_path
        else:
            command = f"powershell -File {entry.rel_path}"
        entries.append(
            StartupEntry(
                source="script",
                path=entry.rel_path,
                command=command,
                verified=name in readme_text or entry.rel_path.lower() in readme_text,
                detail="仓库自带启动脚本",
            )
        )
        if len(entries) >= 6:
            break
    return entries


def _collect_env_vars(ctx: AnalyzerContext) -> tuple[list[str], bool]:
    names: set[str] = set()
    env_example = False
    for entry in ctx.index.root_files():
        lower = entry.rel_path.lower()
        if lower in {".env.example", ".env.sample", ".env.template", ".env.dist"}:
            env_example = True
            text = ctx.index.text_for(entry) or ""
            for match in ENV_ASSIGNMENT_RE.finditer(text):
                names.add(match.group(1))
    scanned = 0
    for entry, text in ctx.index.iter_text_entries():
        if file_scope(entry.rel_path) in {"docs", "test"}:
            continue
        scanned += 1
        if scanned > 1000:
            break
        for pattern in ENV_CODE_PATTERNS:
            for match in pattern.finditer(text):
                names.add(match.group(1))
                if len(names) >= 40:
                    break
        if len(names) >= 40:
            break
    return sorted(names)[:40], env_example


def analyze_startup(ctx: AnalyzerContext) -> AnalyzerOutput:
    entries: list[StartupEntry] = []
    reasons: list[str] = []
    mismatches: list[str] = []
    package_scripts: dict[str, str] = {}
    package_manager = _package_manager(ctx)
    package_json = _root_text(ctx, "package.json")
    if package_json:
        try:
            data = json.loads(package_json)
            scripts = data.get("scripts") or {}
            if isinstance(scripts, dict):
                package_scripts = {
                    str(key): str(value) for key, value in scripts.items()
                }
        except (json.JSONDecodeError, TypeError):
            scripts = {}
    readme_commands = _extract_readme_commands(ctx.readme_text)
    verified_commands: set[str] = set()
    for key in ("start", "dev", "serve"):
        if key in package_scripts:
            entries.append(
                StartupEntry(
                    source="package_script",
                    path="package.json",
                    command=f"{package_manager} run {key}",
                    verified=False,
                    detail=package_scripts[key][:200],
                )
            )
    if "build" in package_scripts:
        entries.append(
            StartupEntry(
                source="package_script",
                path="package.json",
                command=f"{package_manager} run build",
                verified=False,
                detail=package_scripts["build"][:200],
            )
        )

    makefile = ctx.index.find_root("Makefile", "makefile")
    makefile_text = ctx.index.text_for(makefile) if makefile else None
    make_targets: list[str] = []
    if makefile_text:
        targets = re.findall(r"(?m)^([A-Za-z0-9_.-]+)\s*:", makefile_text)
        make_targets = [
            target
            for target in targets
            if target.lower() in {"run", "start", "dev", "serve", "up", "build"}
        ]
        for target in make_targets:
            entries.append(
                StartupEntry(
                    source="makefile",
                    path=makefile.rel_path,
                    command=f"make {target}",
                    verified=False,
                    detail="Makefile target",
                )
            )

    dockerfile = None
    for name in ("Dockerfile", "dockerfile"):
        dockerfile = ctx.index.find_root(name)
        if dockerfile:
            break
    if dockerfile is None:
        for entry in ctx.index.entries:
            if PurePosixPath(entry.rel_path).name.lower() == "dockerfile":
                dockerfile = entry
                break
    dockerfile_text = ctx.index.text_for(dockerfile) if dockerfile else None
    has_docker = bool(dockerfile)
    if dockerfile_text:
        cmd_match = re.search(
            r"(?im)^\s*(CMD|ENTRYPOINT)\s+(.+)$", dockerfile_text
        )
        entries.append(
            StartupEntry(
                source="dockerfile",
                path=dockerfile.rel_path,
                command="docker build .",
                verified=False,
                detail=(cmd_match.group(0).strip()[:200] if cmd_match else "Dockerfile"),
            )
        )

    compose_entry = None
    compose_names = (
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    )
    compose_entry = ctx.index.find_root(*compose_names)
    has_compose = bool(compose_entry)
    if compose_entry:
        entries.append(
            StartupEntry(
                source="compose",
                path=compose_entry.rel_path,
                command="docker compose up",
                verified=False,
                detail="Compose services",
            )
        )

    procfile = ctx.index.find_root("Procfile")
    procfile_text = ctx.index.text_for(procfile) if procfile else None
    has_procfile = bool(procfile_text)
    if procfile_text:
        for line in procfile_text.splitlines():
            if re.match(r"^\s*web\s*:", line):
                entries.append(
                    StartupEntry(
                        source="procfile",
                        path=procfile.rel_path,
                        command=line.split(":", 1)[1].strip()[:200],
                        verified=False,
                        detail="Procfile web process",
                    )
                )
                break

    pyproject = ctx.index.find_root("pyproject.toml")
    pyproject_text = ctx.index.text_for(pyproject) if pyproject else None
    if pyproject_text:
        try:
            data = tomllib.loads(pyproject_text)
            project_scripts = (data.get("project") or {}).get("scripts") or {}
            poetry_scripts = ((data.get("tool") or {}).get("poetry") or {}).get("scripts") or {}
            for name in list(project_scripts)[:5] + list(poetry_scripts)[:5]:
                entries.append(
                    StartupEntry(
                        source="pyproject",
                        path=pyproject.rel_path,
                        command=str(name),
                        verified=False,
                        detail="pyproject console script",
                    )
                )
        except tomllib.TOMLDecodeError:
            pass

    entries.extend(_script_start_entries(ctx))

    for command in readme_commands:
        entries.append(
            StartupEntry(
                source="readme",
                path=ctx.readme.path if ctx.readme else "README",
                command=command,
                verified=False,
                detail="README 文档命令",
            )
        )

    # Cross-check README package-manager commands against package.json scripts.
    for command in readme_commands:
        match = re.match(
            r"^(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?([A-Za-z0-9:_-]+)$", command.strip()
        )
        if match:
            script_name = match.group(1)
            if script_name in package_scripts:
                verified_commands.add(command)
            else:
                mismatches.append(
                    f"README 要求执行 `{command}`，但 package.json scripts 中不存在 `{script_name}`"
                )
    for entry in entries:
        if entry.command in verified_commands:
            entry.verified = True
            entry.detail = (entry.detail + " · README 已引用").strip(" ·")

    has_source = any(file_scope(entry.rel_path) == "source" for entry in ctx.index.entries)
    explicit_entries = [entry for entry in entries if entry.source != "readme"]
    explicit_start = any(
        entry.source in {"package_script", "makefile", "compose", "procfile", "script"}
        and not (
            entry.source == "package_script"
            and entry.command.endswith("run build")
        )
        for entry in explicit_entries
    ) or any(entry.source == "dockerfile" for entry in explicit_entries)
    has_build = (
        "build" in package_scripts
        or any(target == "build" for target in make_targets)
        or bool(dockerfile)
        or bool(BUILD_COMMAND_RE.search(ctx.readme_text or ""))
    )
    env_vars, env_example = _collect_env_vars(ctx)

    score = 0
    if explicit_start:
        score += 40
        reasons.append("提供可执行的启动脚本（+40）")
    if readme_commands:
        score += 25
        reasons.append("README 记录了启动命令（+25）")
    if has_build:
        score += 15
        reasons.append("提供构建步骤（+15）")
    if has_docker or has_compose or has_procfile:
        score += 10
        reasons.append("提供容器/进程启动方式（+10）")
    has_quickstart = bool(
        ctx.readme
        and any(
            check.key == "usage" and check.present for check in ctx.readme.sections
        )
    )
    if has_quickstart:
        score += 10
        reasons.append("README 有使用/快速开始章节（+10）")
    score = min(100, score)

    risks = []
    if has_source and not explicit_start and not readme_commands:
        risks.append(
            build_risk(
                rule_id="START-MISSING",
                dimension="startup",
                category="startup",
                severity="high",
                title="未发现可执行的启动方式",
                description="仓库包含源码，但没有启动脚本、容器配置或可核实的运行命令。",
                recommendation="补充启动脚本（package.json scripts / Makefile / Docker）并在 README 写明命令。",
                confidence="high",
                blocking=True,
            )
        )
    elif has_source and not explicit_start and readme_commands:
        risks.append(
            build_risk(
                rule_id="START-DOCS-ONLY",
                dimension="startup",
                category="startup",
                severity="medium",
                title="启动命令仅存在于 README",
                description="README 记录了运行命令，但仓库没有对应的启动脚本或容器配置，命令可能已经失效。",
                recommendation="把可执行命令固化到 package.json scripts、Makefile 或 Docker Compose，并保持文档同步。",
                path=ctx.readme.path if ctx.readme else None,
                evidence=readme_commands[0],
                source_url=ctx.source_url(ctx.readme.path if ctx.readme else None, 1),
                confidence="medium",
            )
        )
    elif readme_commands and explicit_start and not verified_commands:
        risks.append(
            build_risk(
                rule_id="START-UNVERIFIED",
                dimension="startup",
                category="startup",
                severity="low",
                title="README 启动命令未能与脚本核对",
                description="README 中存在启动命令，但无法确认它们与仓库脚本完全一致。",
                recommendation="在 README 中优先引用 package.json / Makefile 中真实存在的命令。",
                evidence=readme_commands[0],
                path=ctx.readme.path if ctx.readme else None,
                source_url=ctx.source_url(ctx.readme.path if ctx.readme else None, 1),
                confidence="low",
            )
        )
    if mismatches:
        risks.append(
            build_risk(
                rule_id="START-MISMATCH",
                dimension="startup",
                category="startup",
                severity="medium",
                title="README 启动命令与 package.json 不一致",
                description="按 README 执行可能直接失败，导致接入体验受阻。",
                recommendation="修正 README 或补充缺失的 npm script。",
                evidence=mismatches[0],
                path="package.json",
                source_url=ctx.source_url("package.json", 1),
                occurrences=len(mismatches),
                confidence="high",
            )
        )
    if env_vars and not env_example and not (ctx.readme and ctx.readme.has_config):
        risks.append(
            build_risk(
                rule_id="START-ENV-UNDOCUMENTED",
                dimension="startup",
                category="startup",
                severity="medium",
                title="项目依赖环境变量但缺少说明",
                description=f"代码至少引用 {len(env_vars)} 个环境变量，但未发现 .env.example 或配置章节。",
                recommendation="提供 .env.example，并在 README 说明每个必需变量的用途。",
                evidence=", ".join(env_vars[:8]),
                confidence="high",
            )
        )
    if env_vars and env_example:
        reasons.append("发现 .env.example（配置可发现性 +）")

    suggested: str | None = None
    for key in ("dev", "start", "serve"):
        if key in package_scripts:
            suggested = f"{package_manager} run {key}"
            break
    if not suggested and has_compose:
        suggested = "docker compose up"
    if not suggested:
        for target in ("run", "start", "dev"):
            if target in make_targets:
                suggested = f"make {target}"
                break
    if not suggested:
        for entry in entries:
            if entry.source == "script" and (entry.path or "").lower().endswith(".sh"):
                suggested = entry.command
                break
    if not suggested and readme_commands:
        suggested = readme_commands[0]
    if not suggested:
        for entry in entries:
            if entry.source == "script":
                suggested = entry.command
                break
    if not suggested and dockerfile:
        suggested = "docker build ."

    summary = (
        "已找到明确的启动路径。"
        if explicit_start
        else ("仅有文档中的启动命令，建议固化为脚本。"
              if readme_commands
              else ("包含源码但缺少可执行启动方式。" if has_source else "未发现应用启动需求。"))
    )
    section = StartupSection(
        entries=entries,
        documented_commands=readme_commands,
        env_vars=env_vars,
        env_example=env_example,
        has_docker=has_docker,
        has_compose=has_compose,
        has_procfile=has_procfile,
        has_makefile=bool(makefile_text),
        suggested_command=suggested,
        mismatches=mismatches,
        score=score,
        summary=summary,
    )
    ctx.startup = section
    return AnalyzerOutput(section=section, risks=risks, score=score, reasons=reasons)
