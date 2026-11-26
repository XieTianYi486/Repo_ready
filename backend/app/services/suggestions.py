from __future__ import annotations

from ..models import ReportSections, Risk


def build_suggestions(risks: list[Risk], sections: ReportSections) -> list[str]:
    suggestions: list[str] = []

    def add(text: str) -> None:
        if text not in suggestions and len(suggestions) < 6:
            suggestions.append(text)

    security_risks = [risk for risk in risks if risk.dimension == "security"]
    if any(risk.severity in {"critical", "high"} for risk in security_risks):
        add("先停用并轮换所有已泄露的凭据，再从仓库和历史记录中清理，最后补上 .gitignore。")
    if sections.secrets.env_files or (
        sections.startup.env_example and not sections.secrets.gitignore_env
    ):
        add("把 .env 加入 .gitignore，仅提交 .env.example，并检查历史提交是否包含真实值。")
    if not sections.readme.present:
        add("补齐 README：项目简介、安装命令、启动命令、配置说明与许可证。")
    elif not (sections.readme.has_install and sections.readme.has_usage):
        add("在 README 中补充安装/快速开始与使用章节，并给出可直接复制的命令。")
    if not sections.startup.suggested_command:
        add("把启动方式固化为 package.json scripts、Makefile 或 Docker Compose，并写进 README。")
    if not sections.dependencies.has_manifest:
        add("补充标准依赖清单并锁定版本，确保接入方可复现安装。")
    elif not sections.dependencies.lockfiles:
        add("提交依赖锁文件（package-lock.json / poetry.lock / go.sum 等），避免版本漂移。")
    if sections.paths.counts_by_severity.get("high", 0) > 0:
        add("把源码/配置中的绝对路径改为环境变量或相对路径，避免换机即失效。")
    if sections.windows.only_windows_start:
        add("增加 .sh / Makefile / Docker 等跨平台启动方式，避免只能在一台 Windows 机器上运行。")
    if sections.startup.env_vars and not sections.startup.env_example:
        add("补充 .env.example 与 README 配置章节，列出必需环境变量及默认值。")

    return suggestions
