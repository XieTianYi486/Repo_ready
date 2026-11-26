from __future__ import annotations

import json
import posixpath
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath

from ...models import DependenciesSection, ManifestInfo
from ...utils.text import depth_of
from .common import build_risk, file_scope
from .context import AnalyzerContext, AnalyzerOutput

MANIFEST_KINDS: dict[str, tuple[str, str]] = {
    "package.json": ("npm", "package.json"),
    "composer.json": ("composer", "composer.json"),
    "pyproject.toml": ("python", "pyproject.toml"),
    "pipfile": ("python", "Pipfile"),
    "setup.py": ("python", "setup.py"),
    "setup.cfg": ("python", "setup.cfg"),
    "go.mod": ("go", "go.mod"),
    "cargo.toml": ("rust", "Cargo.toml"),
    "pom.xml": ("java", "pom.xml"),
    "build.gradle": ("java", "build.gradle"),
    "build.gradle.kts": ("java", "build.gradle.kts"),
    "gemfile": ("ruby", "Gemfile"),
    "pubspec.yaml": ("dart", "pubspec.yaml"),
    "package.swift": ("swift", "Package.swift"),
    "environment.yml": ("conda", "environment.yml"),
    "environment.yaml": ("conda", "environment.yml"),
}

LOCKFILE_ECOSYSTEM: dict[str, str] = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "yarn.lock": "npm",
    "pnpm-lock.yaml": "npm",
    "bun.lockb": "npm",
    "poetry.lock": "python",
    "uv.lock": "python",
    "pipfile.lock": "python",
    "go.sum": "go",
    "cargo.lock": "rust",
    "composer.lock": "composer",
    "gemfile.lock": "ruby",
    "packages.lock.json": "dotnet",
    "pubspec.lock": "dart",
}

LOCKFILE_BY_ECOSYSTEM = {
    "npm": ("package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"),
    "python": ("poetry.lock", "uv.lock", "Pipfile.lock"),
    "go": ("go.sum",),
    "rust": ("Cargo.lock",),
    "composer": ("composer.lock",),
    "ruby": ("Gemfile.lock",),
    "dotnet": ("packages.lock.json",),
    "dart": ("pubspec.lock",),
}


def _manifest_kind(path: str) -> tuple[str, str] | None:
    name = PurePosixPath(path).name
    lower = name.lower()
    if lower in MANIFEST_KINDS:
        return MANIFEST_KINDS[lower]
    if lower.startswith("requirements") and lower.endswith(".txt"):
        return "python", name
    if lower.endswith(".csproj"):
        return "dotnet", name
    return None


def _count_requirements(text: str) -> int:
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        count += 1
    return count


def _parse_manifest(kind: str, text: str) -> tuple[bool, int, int, list[str]]:
    issues: list[str] = []
    try:
        if kind == "package.json":
            data = json.loads(text)
            deps = data.get("dependencies") or {}
            dev = data.get("devDependencies") or {}
            peer = data.get("peerDependencies") or {}
            optional = data.get("optionalDependencies") or {}
            total = len(deps) + len(peer) + len(optional)
            return True, total, len(dev), issues
        if kind == "composer.json":
            data = json.loads(text)
            return (
                True,
                len(data.get("require") or {}),
                len(data.get("require-dev") or {}),
                issues,
            )
        if kind == "pyproject.toml":
            data = tomllib.loads(text)
            project = data.get("project") or {}
            deps = project.get("dependencies") or []
            optional = project.get("optional-dependencies") or {}
            dev = sum(len(value) for value in optional.values()) if isinstance(optional, dict) else 0
            if not deps and isinstance(data.get("tool"), dict):
                poetry = data["tool"].get("poetry") or {}
                if isinstance(poetry, dict):
                    deps = [
                        key
                        for key in (poetry.get("dependencies") or {})
                        if key.lower() != "python"
                    ]
                    dev = len(poetry.get("dev-dependencies") or {})
            return True, len(deps), dev, issues
        if kind.lower() == "pipfile":
            data = tomllib.loads(text)
            return (
                True,
                len(data.get("packages") or {}),
                len(data.get("dev-packages") or {}),
                issues,
            )
        if kind == "requirements.txt" or kind.lower().startswith("requirements"):
            return True, _count_requirements(text), 0, issues
        if kind == "setup.py":
            count = len(re.findall(r"['\"][A-Za-z0-9_.-]+\s*[<>=!~]", text))
            return True, count, 0, issues
        if kind == "setup.cfg":
            in_requires = False
            count = 0
            for line in text.splitlines():
                if re.match(r"^\s*install_requires\s*=", line, re.IGNORECASE):
                    in_requires = True
                    continue
                if in_requires:
                    if line.strip() and not line.startswith((" ", "\t")):
                        in_requires = False
                        continue
                    if line.strip():
                        count += 1
            return True, count, 0, issues
        if kind == "go.mod":
            count = 0
            in_block = False
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("require ("):
                    in_block = True
                    continue
                if in_block and stripped == ")":
                    in_block = False
                    continue
                if in_block and stripped and not stripped.startswith("//"):
                    count += 1
                elif stripped.startswith("require ") and not stripped.endswith("("):
                    count += 1
            return True, count, 0, issues
        if kind == "Cargo.toml":
            data = tomllib.loads(text)
            return (
                True,
                len(data.get("dependencies") or {}),
                len(data.get("dev-dependencies") or {}),
                issues,
            )
        if kind == "pom.xml":
            root = ET.fromstring(text)
            count = sum(
                1
                for element in root.iter()
                if element.tag.split("}")[-1].lower() == "dependency"
            )
            return True, count, 0, issues
        if kind in {"build.gradle", "build.gradle.kts"}:
            count = len(
                re.findall(
                    r"(?m)^\s*(?:implementation|api|compileOnly|runtimeOnly|testImplementation|kapt)\s*\(",
                    text,
                )
            )
            return True, count, 0, issues
        if kind.lower() == "gemfile":
            count = len(re.findall(r"(?m)^\s*gem\s+['\"]", text))
            return True, count, 0, issues
        if kind.lower().endswith(".csproj"):
            root = ET.fromstring(text)
            count = sum(
                1
                for element in root.iter()
                if element.tag.split("}")[-1].lower() == "packagereference"
            )
            return True, count, 0, issues
        if kind.lower() == "pubspec.yaml":
            in_deps = False
            count = 0
            for line in text.splitlines():
                if re.match(r"^dependencies:\s*$", line):
                    in_deps = True
                    continue
                if in_deps:
                    if line and not line.startswith((" ", "\t")):
                        in_deps = False
                        continue
                    if re.match(r"^\s{2}[A-Za-z0-9_-]+:", line):
                        count += 1
            return True, count, 0, issues
        if kind.lower() == "package.swift":
            return True, len(re.findall(r"\.package\s*\(", text)), 0, issues
        if kind.lower() == "environment.yml":
            in_deps = False
            count = 0
            for line in text.splitlines():
                if re.match(r"^dependencies:\s*$", line):
                    in_deps = True
                    continue
                if in_deps:
                    if line and not line.startswith((" ", "\t", "-")):
                        in_deps = False
                        continue
                    if re.match(r"^\s*-\s+[A-Za-z0-9_.-]+", line):
                        count += 1
            return True, count, 0, issues
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, ET.ParseError, ValueError) as exc:
        issues.append(f"解析失败：{exc.__class__.__name__}")
        return False, 0, 0, issues
    except Exception as exc:  # Defensive: never fail the whole scan on one manifest.
        issues.append(f"解析异常：{exc.__class__.__name__}")
        return False, 0, 0, issues
    return True, 0, 0, issues


def _lockfile_for(path: str, ecosystems: set[str], rel_paths: set[str]) -> str | None:
    directory = posixpath.dirname(path)
    for ecosystem in ecosystems:
        for name in LOCKFILE_BY_ECOSYSTEM.get(ecosystem, ()):
            candidate = posixpath.join(directory, name) if directory else name
            if candidate in rel_paths:
                return candidate
    return None


def analyze_dependencies(ctx: AnalyzerContext) -> AnalyzerOutput:
    index = ctx.index
    rel_paths = {entry.rel_path for entry in index.entries}
    manifests: list[ManifestInfo] = []
    lockfiles: list[str] = []
    ecosystems: set[str] = set()
    primary_manifests: list[ManifestInfo] = []
    code_file_count = 0
    for entry in index.entries:
        if file_scope(entry.rel_path) == "source":
            code_file_count += 1
        lock_name = PurePosixPath(entry.rel_path).name.lower()
        if lock_name in LOCKFILE_ECOSYSTEM:
            lockfiles.append(entry.rel_path)
            ecosystems.add(LOCKFILE_ECOSYSTEM[lock_name])
            continue
        kind_info = _manifest_kind(entry.rel_path)
        if not kind_info:
            continue
        ecosystem, kind = kind_info
        text = index.text_for(entry) or ""
        parse_ok, deps, dev, issues = _parse_manifest(kind, text)
        scope = file_scope(entry.rel_path)
        primary = scope not in {"test", "docs"} and depth_of(entry.rel_path) <= 2
        manifest = ManifestInfo(
            path=entry.rel_path,
            ecosystem=ecosystem,
            kind=kind,
            parse_ok=parse_ok,
            dependency_count=deps,
            dev_dependency_count=dev,
            lockfile=None,
            issues=issues,
            primary=primary,
        )
        manifests.append(manifest)
        ecosystems.add(ecosystem)
        if primary:
            primary_manifests.append(manifest)

    for manifest in manifests:
        manifest.lockfile = _lockfile_for(
            manifest.path, {manifest.ecosystem}, rel_paths
        )
    lockfiles = sorted(set(lockfiles))

    risks = []
    reasons: list[str] = []
    if not manifests:
        score = 0
        severity = "high" if code_file_count > 0 else "low"
        risks.append(
            build_risk(
                rule_id="DEP-MISSING-MANIFEST",
                dimension="dependencies",
                category="dependencies",
                severity=severity,
                title="缺少依赖清单",
                description=(
                    "存在源码文件，但未发现 package.json、requirements.txt、go.mod 等依赖清单。"
                    if code_file_count > 0
                    else "未发现依赖清单，项目可能仅包含文档或静态资源。"
                ),
                recommendation="补充标准依赖清单并锁定版本，确保接入方可复现安装。",
                confidence="high",
            )
        )
        reasons.append("未发现依赖清单（+0）")
        summary = "未发现依赖清单。"
    else:
        parsed_primary = [m for m in primary_manifests if m.parse_ok]
        score = 50 if parsed_primary else 20
        reasons.append(
            "发现依赖清单" + ("且可解析（+50）" if parsed_primary else "但无法解析（+20）")
        )
        if lockfiles:
            score += 20
            reasons.append("存在锁文件（+20）")
        else:
            reasons.append("未发现锁文件（+0）")
        if any(m.parse_ok for m in manifests):
            score += 20
            reasons.append("依赖清单可解析（+20）")
        else:
            reasons.append("依赖清单不可解析（+0）")
        if len(ecosystems) >= 2 or (ctx.readme and ctx.readme.has_install):
            score += 10
            reasons.append("多生态或 README 有安装说明（+10）")
        score = min(100, score)
        for manifest in manifests:
            if manifest.primary and not manifest.parse_ok:
                risks.append(
                    build_risk(
                        rule_id="DEP-MANIFEST-INVALID",
                        dimension="dependencies",
                        category="dependencies",
                        severity="high",
                        title=f"依赖清单无法解析：{manifest.path}",
                        description="接入方无法据此稳定安装依赖。",
                        recommendation="修复该清单的语法错误，并提供锁文件。",
                        path=manifest.path,
                        evidence="；".join(manifest.issues) or "解析失败",
                        source_url=ctx.source_url(manifest.path, 1),
                        confidence="high",
                    )
                )
        if not lockfiles:
            risks.append(
                build_risk(
                    rule_id="DEP-NO-LOCKFILE",
                    dimension="dependencies",
                    category="dependencies",
                    severity="low",
                    title="缺少依赖锁文件",
                    description="依赖版本可能漂移，接入方难以复现完全一致的环境。",
                    recommendation="提交 package-lock.json / poetry.lock / go.sum 等锁文件。",
                    path=manifests[0].path if manifests else None,
                    evidence="未发现锁文件",
                    source_url=ctx.source_url(manifests[0].path, 1) if manifests else None,
                    confidence="high",
                )
            )
        if manifests and ctx.readme and not ctx.readme.has_install:
            risks.append(
                build_risk(
                    rule_id="DEP-NO-INSTALL-DOCS",
                    dimension="dependencies",
                    category="dependencies",
                    severity="medium",
                    title="声明了依赖但缺少安装说明",
                    description="README 未提供安装步骤，接入方需要自行推断依赖安装方式。",
                    recommendation="在 README 补充安装命令，并与依赖清单保持一致。",
                    path=manifests[0].path,
                    evidence="README 未识别到安装章节",
                    source_url=ctx.source_url(manifests[0].path, 1),
                    confidence="medium",
                )
            )
        managers = {
            manager
            for manager in (
                "npm" if any(m.kind == "package.json" for m in manifests) else None,
                "python" if any(m.ecosystem == "python" for m in manifests) else None,
            )
            if manager
        }
        if len(managers) >= 2 and len(lockfiles) >= 2:
            risks.append(
                build_risk(
                    rule_id="DEP-MULTI-MANAGER",
                    dimension="dependencies",
                    category="dependencies",
                    severity="low",
                    title="多种包管理器锁文件并存",
                    description="仓库同时存在多种包管理器锁文件，可能造成安装方式不一致。",
                    recommendation="明确主包管理器，并在 README 中统一安装命令。",
                    evidence=", ".join(lockfiles[:5]),
                    source_url=ctx.source_url(lockfiles[0], 1) if lockfiles else None,
                    confidence="medium",
                )
            )
        summary = (
            f"发现 {len(manifests)} 个依赖清单、{len(lockfiles)} 个锁文件，"
            f"覆盖 {len(ecosystems)} 个生态。"
        )

    section = DependenciesSection(
        manifests=manifests,
        ecosystems=sorted(ecosystems),
        lockfiles=lockfiles,
        has_manifest=bool(manifests),
        score=score,
        summary=summary,
    )
    return AnalyzerOutput(section=section, risks=risks, score=score, reasons=reasons)
