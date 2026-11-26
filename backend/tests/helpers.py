from __future__ import annotations

import shutil
from pathlib import Path

from backend.app.config import RULES_VERSION, SCHEMA_VERSION, TOOL_VERSION
from backend.app.models import (
    AiAdvice,
    CommitInfo,
    Report,
    ReportSections,
    RepoInfo,
    SnapshotInfo,
    UpdateInfo,
)
from backend.app.services.analyzers.context import AnalyzerContext
from backend.app.services.analyzers.dependencies import analyze_dependencies
from backend.app.services.analyzers.paths import analyze_paths
from backend.app.services.analyzers.readme import analyze_readme
from backend.app.services.analyzers.secrets import analyze_secrets
from backend.app.services.analyzers.startup import analyze_startup
from backend.app.services.analyzers.windows_scripts import analyze_windows
from backend.app.services.file_index import build_file_index
from backend.app.services.platform.gitee import GiteeAdapter
from backend.app.services.platform.github import GitHubAdapter
from backend.app.services.platform.parser import parse_repo_url
from backend.app.services.scan_service import make_report_id
from backend.app.services.scoring import aggregate_risks, build_score
from backend.app.services.suggestions import build_suggestions
from backend.app.utils.text import utc_now_iso

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "repos" / "demo_repo"
SHA = "a" * 40


def copy_demo_repo(tmp_path: Path) -> Path:
    target = tmp_path / "repo"
    shutil.copytree(FIXTURE_ROOT, target)
    return target


def make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    root.mkdir(parents=True, exist_ok=True)
    for rel_path, content in files.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def build_context(root: Path, platform: str = "github") -> AnalyzerContext:
    url = (
        "https://gitee.com/demo/demo-repo"
        if platform == "gitee"
        else "https://github.com/demo/demo-repo"
    )
    parsed = parse_repo_url(url)
    repo = RepoInfo(
        platform=platform,
        owner="demo",
        name="demo-repo",
        full_name="demo/demo-repo",
        html_url=parsed.html_url,
        default_branch="main",
        description="Fixture",
        stars=1,
        forks=1,
        language="JavaScript",
        license="MIT",
    )
    commit = CommitInfo(
        sha=SHA,
        short_sha=SHA[:7],
        branch="main",
        message="fixture",
        author="tester",
        url=f"{parsed.html_url}/commit/{SHA}",
    )
    adapter = GiteeAdapter() if platform == "gitee" else GitHubAdapter()
    index = build_file_index(
        root,
        max_files=5000,
        max_text_file_bytes=512 * 1024,
        max_total_text_bytes=20 * 1024 * 1024,
    )
    return AnalyzerContext(
        parsed=parsed,
        repo=repo,
        commit=commit,
        index=index,
        adapter=adapter,
    )


def analyze_all(ctx: AnalyzerContext) -> dict:
    readme = analyze_readme(ctx)
    ctx.readme = readme.section
    dependencies = analyze_dependencies(ctx)
    startup = analyze_startup(ctx)
    windows = analyze_windows(ctx)
    paths = analyze_paths(ctx)
    secrets = analyze_secrets(ctx)
    return {
        "readme": readme,
        "dependencies": dependencies,
        "startup": startup,
        "windows": windows,
        "paths": paths,
        "secrets": secrets,
    }


def build_report(root: Path, platform: str = "github") -> Report:
    ctx = build_context(root, platform)
    outputs = analyze_all(ctx)
    risks = aggregate_risks(
        [
            *outputs["readme"].risks,
            *outputs["dependencies"].risks,
            *outputs["startup"].risks,
            *outputs["windows"].risks,
            *outputs["paths"].risks,
            *outputs["secrets"].risks,
        ]
    )
    identity = (
        f"{ctx.parsed.platform}:{ctx.parsed.full_name.lower()}@{ctx.commit.sha}:"
        f"{RULES_VERSION}:{SCHEMA_VERSION}"
    )
    score = build_score(
        readme=outputs["readme"],
        dependencies=outputs["dependencies"],
        startup=outputs["startup"],
        windows=outputs["windows"],
        paths=outputs["paths"],
        secrets=outputs["secrets"],
        risks=risks,
        identity=identity,
    )
    sections = ReportSections(
        readme=outputs["readme"].section,
        dependencies=outputs["dependencies"].section,
        startup=outputs["startup"].section,
        windows=outputs["windows"].section,
        paths=outputs["paths"].section,
        secrets=outputs["secrets"].section,
    )
    report_id = make_report_id(ctx.parsed, "main", ctx.commit.sha)
    return Report(
        id=report_id,
        schema_version=SCHEMA_VERSION,
        tool_version=TOOL_VERSION,
        rules_version=RULES_VERSION,
        platform=ctx.parsed.platform,
        repo=ctx.repo,
        commit=ctx.commit,
        analyzed_at=utc_now_iso(),
        duration_ms=42,
        cached=False,
        score=score,
        sections=sections,
        risks=risks,
        suggestions=build_suggestions(risks, sections),
        ai=AiAdvice(status="disabled"),
        update=UpdateInfo(),
        limits=SnapshotInfo(
            compressed_bytes=1000,
            extracted_bytes=2000,
            files_total=len(ctx.index.entries),
            files_scanned=len(ctx.index.entries),
            files_skipped=ctx.index.files_skipped,
            text_bytes_scanned=ctx.index.text_bytes_scanned,
            truncated=ctx.index.truncated,
            warnings=list(ctx.index.warnings),
        ),
        project=ctx.index.project_info(),
    )
