from __future__ import annotations

from ..models import Report
from ..utils.text import safe_filename

SEVERITY_LABELS = {
    "critical": "严重",
    "high": "高",
    "medium": "中",
    "low": "低",
    "info": "信息",
}


def _cell(value: str | None, limit: int = 180) -> str:
    text = (value or "").replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def export_filename(report: Report, suffix: str) -> str:
    base = safe_filename(f"repoready-{report.repo.full_name}-{report.commit.short_sha}")
    return f"{base}.{suffix}"


def render_markdown(report: Report) -> str:
    lines: list[str] = []
    lines.append(f"# RepoReady 体检报告 · {report.repo.full_name}")
    lines.append("")
    lines.append(f"- 平台：{report.platform}")
    lines.append(f"- 仓库：{report.repo.html_url}")
    lines.append(f"- 分支：{report.commit.branch}")
    lines.append(f"- 基于 commit：`{report.commit.sha}`（{report.commit.short_sha}）")
    lines.append(f"- 分析时间：{report.analyzed_at}")
    lines.append(f"- 扫描耗时：{report.duration_ms / 1000:.1f}s")
    lines.append(f"- 规则版本：{report.rules_version}")
    lines.append("")
    description = (report.repo.description or "").strip()
    if description:
        lines.append(description)
        lines.append("")

    lines.append("## 接入就绪度")
    lines.append("")
    lines.append(
        f"**{report.score.total} / 100 · {report.score.grade} 级 · {report.score.label}**"
    )
    if report.score.capped:
        lines.append("")
        lines.append("> 评分封顶：" + "；".join(report.score.cap_reason))
    lines.append("")
    lines.append("| 维度 | 得分 | 权重 | 加权 | 状态 | 摘要 |")
    lines.append("|---|---:|---:|---:|---|---|")
    for dimension in report.score.dimensions:
        lines.append(
            f"| {dimension.name} | {dimension.score} | {dimension.weight} | "
            f"{dimension.weighted} | {dimension.status} | {_cell(dimension.summary)} |"
        )
    lines.append("")

    lines.append("## 主要风险")
    lines.append("")
    if not report.risks:
        lines.append("未发现需要处理的风险。")
    else:
        lines.append("| 严重度 | 维度 | 风险 | 位置 | 建议 |")
        lines.append("|---|---|---|---|---|")
        for risk in report.risks[:20]:
            location = risk.file or ""
            if risk.line:
                location += f":{risk.line}"
            if risk.source_url:
                location = f"[{_cell(location)}]({risk.source_url})"
            lines.append(
                f"| {SEVERITY_LABELS.get(risk.severity, risk.severity)} "
                f"| {risk.dimension} | {_cell(risk.title)} | {_cell(location)} "
                f"| {_cell(risk.recommendation)} |"
            )
    lines.append("")

    lines.append("## 检测摘要")
    lines.append("")
    lines.append(f"- README：{_cell(report.sections.readme.summary, 300)}")
    lines.append(f"- 依赖：{_cell(report.sections.dependencies.summary, 300)}")
    lines.append(f"- 启动：{_cell(report.sections.startup.summary, 300)}")
    lines.append(f"- Windows 脚本：{_cell(report.sections.windows.summary, 300)}")
    lines.append(f"- 硬编码路径：{_cell(report.sections.paths.summary, 300)}")
    lines.append(f"- 敏感信息：{_cell(report.sections.secrets.summary, 300)}")
    lines.append("")
    if report.sections.startup.suggested_command:
        lines.append(
            f"建议启动命令：`{report.sections.startup.suggested_command}`"
        )
        lines.append("")

    lines.append("## 下一步建议")
    lines.append("")
    if report.suggestions:
        for suggestion in report.suggestions:
            lines.append(f"- {suggestion}")
    else:
        lines.append("- 暂无明显需要补强的项。")
    lines.append("")

    if report.ai.status == "ready":
        lines.append("## AI 建议（不影响主评分）")
        lines.append("")
        if report.ai.summary:
            lines.append(report.ai.summary)
            lines.append("")
        if report.ai.reference_score is not None:
            lines.append(
                f"AI 参考分：**{report.ai.reference_score} / 100**（仅供参考，不参与确定性评分）"
            )
            lines.append("")
        if report.ai.score_reason:
            lines.append(f"> {report.ai.score_reason}")
            lines.append("")
        if report.ai.blockers:
            lines.append("### 阻断项")
            for blocker in report.ai.blockers:
                lines.append(
                    f"- **{blocker.title}**（{blocker.severity}）：{blocker.why} 建议：{blocker.fix}"
                )
            lines.append("")
        if report.ai.quick_wins:
            lines.append("### 快速收益")
            for item in report.ai.quick_wins:
                lines.append(f"- {item.action}：{item.effect}")
            lines.append("")
        if report.ai.integration_plan:
            lines.append("### 接入步骤")
            for step in report.ai.integration_plan:
                lines.append(f"{step.step}. {step.detail}")
            lines.append("")
        if report.ai.caveats:
            lines.append("### 注意事项")
            for caveat in report.ai.caveats:
                lines.append(f"- {caveat}")
            lines.append("")
    elif report.ai.status == "error":
        lines.append("## AI 建议")
        lines.append("")
        lines.append(f"AI 建议生成失败：{report.ai.error or '未知错误'}")
        lines.append("")

    lines.append("---")
    lines.append(
        f"由 RepoReady {report.tool_version} 生成 · 规则 {report.rules_version} · "
        f"公式 {report.score.formula_version} · 指纹 `{report.score.fingerprint}`"
    )
    lines.append("")
    lines.append(
        "> 安全说明：仅做静态扫描，不执行仓库代码；所有密钥/敏感值均已脱敏。"
        "评分为启发式规则结果，接入前请结合人工审查。"
    )
    return "\n".join(lines)
