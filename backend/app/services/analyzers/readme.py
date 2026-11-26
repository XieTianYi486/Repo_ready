from __future__ import annotations

import re

from ...models import ReadmeSection, SectionCheck
from ...utils.text import strip_html_comments
from .common import build_risk
from .context import AnalyzerContext, AnalyzerOutput

SECTION_DEFS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "install",
        "安装 / 快速开始",
        re.compile(
            r"(?i)\b(?:installation|install|setup|getting[ -]?started|quick[ -]?start)\b"
            r"|安装|快速开始|部署说明|环境准备"
        ),
    ),
    (
        "usage",
        "使用 / 运行",
        re.compile(
            r"(?i)\b(?:usage|how to run|running|run the app|start the app|quickstart)\b"
            r"|使用说明|如何使用|使用方式|使用|运行|启动"
        ),
    ),
    (
        "config",
        "配置 / 环境变量",
        re.compile(
            r"(?i)\b(?:configuration|config|environment variables?|env vars?|\.env)\b"
            r"|配置|环境变量|参数说明"
        ),
    ),
    (
        "api",
        "API / 架构",
        re.compile(
            r"(?i)\b(?:api|architecture|project structure|directory structure|modules?)\b"
            r"|架构|目录结构|接口文档"
        ),
    ),
    (
        "license",
        "许可证",
        re.compile(r"(?i)\b(?:license|licence)\b|许可证|开源协议|许可协议"),
    ),
)

HEADING_RE = re.compile(r"(?m)^#{1,6}\s+(.+?)\s*$")
FENCE_RE = re.compile(r"(?m)^(?:```|~~~)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
PLACEHOLDER_PATTERNS = (
    "your-project",
    "your_project",
    "your-project-name",
    "<your",
    "yourname",
    "your-name",
    "lorem ipsum",
    "todo:",
    "changeme",
)


def analyze_readme(ctx: AnalyzerContext) -> AnalyzerOutput:
    entry = ctx.index.readme_entry()
    if entry is None:
        section = ReadmeSection(
            present=False,
            score=0,
            summary="未发现 README，接入者缺少最基本的使用说明。",
            sections=[
                SectionCheck(key=key, label=label, present=False)
                for key, label, _pattern in SECTION_DEFS
            ],
        )
        risk = build_risk(
            rule_id="DOC-README-MISSING",
            dimension="readme",
            category="docs",
            severity="high",
            title="缺少 README",
            description="仓库根目录没有 README，无法快速了解项目用途、安装方式与启动命令。",
            recommendation="补充 README，至少包含项目简介、安装步骤、启动命令、配置说明与许可证信息。",
            confidence="high",
            blocking=True,
        )
        return AnalyzerOutput(
            section=section,
            risks=[risk],
            score=0,
            reasons=["缺少 README：文档可读性 0 分"],
        )

    text = ctx.index.text_for(entry) or ""
    ctx.readme_text = text
    clean_text = strip_html_comments(text)
    lower = clean_text.lower()
    headings = [
        match.group(1).strip()[:100]
        for match in HEADING_RE.finditer(clean_text)
    ][:40]
    code_blocks = max(0, len(FENCE_RE.findall(clean_text)) // 2)
    images = len(IMAGE_RE.findall(clean_text))
    badges = len(re.findall(r"(?i)shields\.io|badge\.svg|badgen\.net", clean_text))
    placeholders = [
        token for token in PLACEHOLDER_PATTERNS if token in lower
    ][:8]

    checks: list[SectionCheck] = []
    for key, label, pattern in SECTION_DEFS:
        present = bool(pattern.search(clean_text))
        headings_match = any(
            pattern.search(heading) for heading in headings
        )
        checks.append(
            SectionCheck(key=key, label=label, present=present or headings_match)
        )
    present_map = {check.key: check.present for check in checks}
    has_install = present_map.get("install", False)
    has_usage = present_map.get("usage", False)
    has_config = present_map.get("config", False)
    has_api = present_map.get("api", False)
    has_license = present_map.get("license", False)

    reasons: list[str] = []
    score = 25
    reasons.append("存在 README（+25）")
    chars = len(clean_text.strip())
    if chars >= 500:
        score += 10
        reasons.append("正文 ≥ 500 字符（+10）")
    else:
        reasons.append("正文少于 500 字符（+0）")
    section_count = sum(1 for check in checks if check.present)
    if section_count:
        gained = section_count * 7
        score += gained
        reasons.append(f"覆盖 {section_count}/5 个关键章节（+{gained}）")
    else:
        reasons.append("未识别到关键章节（+0）")
    if code_blocks >= 1:
        score += 15
        reasons.append("包含代码块（+15）")
    else:
        reasons.append("没有代码示例（+0）")
    if has_install and has_usage:
        score += 15
        reasons.append("同时包含安装与使用说明（+15）")
    else:
        reasons.append("安装/使用说明不完整（+0）")
    if placeholders:
        score = max(0, score - 5)
        reasons.append(f"检测到模板占位文本（−5）：{', '.join(placeholders[:3])}")
    score = min(100, max(0, score))

    risks = []
    missing_sections = [
        check.label for check in checks if not check.present and check.key in {"install", "usage"}
    ]
    if missing_sections:
        risks.append(
            build_risk(
                rule_id="DOC-README-QUICKSTART",
                dimension="readme",
                category="docs",
                severity="medium",
                title="README 缺少安装或使用说明",
                description="接入者无法从 README 直接得知如何安装依赖并启动项目。",
                recommendation="补充“安装/快速开始”和“使用/运行”章节，给出可直接执行的命令。",
                path=entry.rel_path,
                evidence="、".join(missing_sections),
                source_url=ctx.source_url(entry.rel_path, 1),
                confidence="high",
            )
        )
    if not has_config:
        risks.append(
            build_risk(
                rule_id="DOC-README-CONFIG",
                dimension="readme",
                category="docs",
                severity="low",
                title="README 缺少配置说明",
                description="未识别到配置或环境变量章节；若项目依赖环境变量，接入成本会上升。",
                recommendation="补充配置章节与 .env.example，说明必需的环境变量与默认值。",
                path=entry.rel_path,
                evidence="未识别到配置/环境变量章节",
                source_url=ctx.source_url(entry.rel_path, 1),
                confidence="medium",
            )
        )
    if code_blocks == 0 or chars < 500:
        risks.append(
            build_risk(
                rule_id="DOC-README-SHALLOW",
                dimension="readme",
                category="docs",
                severity="low",
                title="README 内容偏薄",
                description="README 长度不足或没有可执行示例，接入者需要额外猜测项目用法。",
                recommendation="补充项目简介、目录结构、可运行示例与常见问题。",
                path=entry.rel_path,
                evidence=f"{chars} 字符，{code_blocks} 个代码块",
                source_url=ctx.source_url(entry.rel_path, 1),
                confidence="high",
            )
        )
    if placeholders:
        risks.append(
            build_risk(
                rule_id="DOC-README-PLACEHOLDER",
                dimension="readme",
                category="docs",
                severity="low",
                title="README 含未替换的模板占位文本",
                description="README 仍然保留模板占位内容，说明项目文档尚未完成。",
                recommendation="梳理并替换占位文本，确保项目名称、命令与配置均准确。",
                path=entry.rel_path,
                evidence=", ".join(placeholders[:5]),
                source_url=ctx.source_url(entry.rel_path, 1),
                confidence="high",
            )
        )

    if has_install and has_usage and code_blocks:
        summary = "README 结构完整，安装、使用与示例均具备。"
    elif has_install or has_usage:
        summary = "README 已具备基础说明，但仍有关键章节缺失。"
    else:
        summary = "README 内容不足，缺少安装与使用说明。"

    section = ReadmeSection(
        present=True,
        path=entry.rel_path,
        chars=chars,
        lines=len(clean_text.splitlines()),
        headings=headings,
        code_blocks=code_blocks,
        images=images,
        badges=badges,
        sections=checks,
        has_install=has_install,
        has_usage=has_usage,
        has_config=has_config,
        has_api=has_api,
        has_license=has_license,
        placeholders=placeholders,
        score=score,
        summary=summary,
    )
    return AnalyzerOutput(section=section, risks=risks, score=score, reasons=reasons)
