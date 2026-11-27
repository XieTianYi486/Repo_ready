from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Callable

from ..config import RULES_VERSION, SCHEMA_VERSION, TOOL_VERSION, Settings
from ..errors import ScanError
from ..models import (
    AiAdvice,
    CommitInfo,
    Report,
    ReportSections,
    SnapshotInfo,
    UpdateInfo,
)
from ..utils.fs import make_temp_dir, safe_rmtree
from ..utils.text import sha1_short, utc_now_iso
from .analyzers.context import AnalyzerContext
from .analyzers.dependencies import analyze_dependencies
from .analyzers.paths import analyze_paths
from .analyzers.readme import analyze_readme
from .analyzers.secrets import analyze_secrets
from .analyzers.startup import analyze_startup
from .analyzers.windows_scripts import analyze_windows
from .fetcher import (
    download_archive,
    extract_archive,
    git_clone_repo,
    git_ls_remote_head,
)
from .file_index import build_file_index
from .http_client import HttpClient
from .platform.parser import ParsedRepo
from .platform.registry import get_adapter
from .report_store import ReportStore
from .scoring import aggregate_risks, build_score
from .sparse import SparseResult, build_sparse_snapshot
from .suggestions import build_suggestions

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str, int, str], None]
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,120}$")


def _emit(progress: ProgressFn | None, stage: str, pct: int, message: str) -> None:
    if progress is None:
        return
    try:
        progress(stage, max(0, min(100, pct)), message)
    except Exception:  # Progress reporting must never break the scan.
        logger.debug("progress callback failed", exc_info=True)


def make_report_id(parsed: ParsedRepo, branch: str, sha: str) -> str:
    return sha1_short(
        f"{parsed.platform}:{parsed.full_name.lower()}:{branch}:{sha}:"
        f"{RULES_VERSION}:{SCHEMA_VERSION}",
        16,
    )


def _validate_branch(branch: str) -> None:
    if not BRANCH_RE.match(branch or "") or ".." in branch:
        raise ScanError("INVALID_BRANCH", "分支名不合法", http_status=400)


def _check_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise ScanError(
            "SCAN_TIMEOUT",
            "扫描超过 180 秒限制，已中止；可尝试配置 Token 或稍后重试",
            http_status=504,
        )


class ScanService:
    def __init__(self, settings: Settings, store: ReportStore) -> None:
        self.settings = settings
        self.store = store

    def _load_cached(self, report_id: str, *, force: bool) -> Report | None:
        if force:
            return None
        report = self.store.load_report(report_id)
        if report is None:
            return None
        if report.rules_version != RULES_VERSION or report.schema_version != SCHEMA_VERSION:
            return None
        return report.model_copy(update={"cached": True})

    def _fetch_head_with_fallback(
        self,
        client: HttpClient,
        adapter,
        parsed: ParsedRepo,
        branch: str,
    ) -> CommitInfo:
        try:
            return adapter.fetch_head(client, parsed, branch)
        except ScanError as exc:
            if exc.code == "BRANCH_NOT_FOUND":
                raise
            if parsed.platform == "gitee":
                sha = git_ls_remote_head(parsed, branch)
                if sha:
                    return CommitInfo(
                        sha=sha,
                        short_sha=sha[:7],
                        branch=branch,
                        message="",
                        author="",
                        date=None,
                        url=adapter.commit_url(parsed, sha),
                        source="git",
                        archive_ref="sha",
                        snapshot_warning="Gitee API 获取 HEAD 失败，已使用 git ls-remote 兜底",
                    )
            raise

    def _clone_fallback(
        self,
        parsed: ParsedRepo,
        branch: str,
        temp_dir: Path,
        head: CommitInfo | None,
        archive_error: ScanError,
    ) -> tuple[Path, CommitInfo, int, list[str]]:
        if parsed.platform != "gitee" or not self.settings.gitee_git_fallback:
            raise archive_error
        logger.info(
            "Archive failed for %s (%s); falling back to git clone",
            parsed.full_name,
            archive_error.code,
        )
        try:
            cloned = git_clone_repo(
                parsed,
                branch,
                temp_dir / "git-fallback",
                max_extracted_bytes=self.settings.max_extracted_bytes,
            )
        except ScanError:
            raise archive_error
        sha = cloned.sha or (head.sha if head else "")
        if not sha:
            raise archive_error
        warning = (
            "Gitee 归档接口暂不可用（可能触发反爬），已使用 git clone --depth 1 "
            "获取同一 commit 的只读快照"
            if parsed.platform == "gitee"
            else f"归档获取失败（{archive_error.code}），已使用 git clone 兜底"
        )
        snapshot_warning: str | None = None
        if head and head.sha and sha != head.sha:
            snapshot_warning = (
                "Gitee 归档接口不可用，且分支在扫描期间发生移动；"
                f"报告基于克隆时的 {sha[:7]}，与元数据 HEAD {head.sha[:7]} 不同"
            )
        elif not head:
            snapshot_warning = warning
        if head:
            commit = head.model_copy(
                update={
                    "sha": sha,
                    "short_sha": sha[:7],
                    "source": "git",
                    "archive_ref": "git",
                    "snapshot_warning": snapshot_warning,
                }
            )
        else:
            commit = CommitInfo(
                sha=sha,
                short_sha=sha[:7],
                branch=branch,
                message="",
                author="",
                date=None,
                url=parsed.html_url,
                source="git",
                archive_ref="git",
                snapshot_warning=snapshot_warning,
            )
        return cloned.root, commit, 0, cloned.warnings + [warning]

    def scan(
        self,
        parsed: ParsedRepo,
        *,
        branch: str | None = None,
        force: bool = False,
        progress: ProgressFn | None = None,
    ) -> Report:
        started = time.monotonic()
        deadline = started + self.settings.scan_timeout_seconds
        temp_dir: Path | None = None
        try:
            _emit(progress, "validating", 4, "校验仓库链接与平台")
            adapter = get_adapter(
                parsed.platform,
                github_token=self.settings.github_token,
                gitee_token=self.settings.gitee_token,
            )
            with HttpClient(
                timeout_seconds=float(self.settings.request_timeout_seconds),
                max_redirects=self.settings.max_redirects,
            ) as client:
                _emit(progress, "metadata", 8, "获取仓库元数据与默认分支")
                repo = adapter.fetch_meta(client, parsed)
                chosen_branch = branch or parsed.branch or repo.default_branch
                _validate_branch(chosen_branch)
                _check_deadline(deadline)

                _emit(progress, "metadata", 14, f"获取分支 {chosen_branch} 的最新提交")
                head: CommitInfo | None = self._fetch_head_with_fallback(
                    client, adapter, parsed, chosen_branch
                )
                _check_deadline(deadline)

                report_id = make_report_id(parsed, chosen_branch, head.sha)
                cached = self._load_cached(report_id, force=force)
                if cached is not None:
                    _emit(progress, "done", 100, "命中相同 commit 的缓存报告")
                    return cached

                temp_dir = make_temp_dir(self.settings.data_dir / "tmp", "scan-")
                commit = head
                archive_bytes = 0
                extract_warnings: list[str] = []
                sparse_result: SparseResult | None = None
                sparse_attempted = False
                repo_root: Path | None = None

                def try_sparse(reason: str) -> bool:
                    nonlocal sparse_result, sparse_attempted, repo_root, archive_bytes
                    if sparse_attempted:
                        return False
                    sparse_attempted = True
                    _emit(progress, "extracting", 35, f"仓库较大，尝试稀疏快照：{reason}")
                    try:
                        result = build_sparse_snapshot(
                            client,
                            adapter,
                            parsed,
                            head.sha,
                            temp_dir / "sparse",
                        )
                    except ScanError as sparse_error:
                        extract_warnings.append(f"稀疏快照失败：{sparse_error.message}")
                        _emit(progress, "extracting", 40, "稀疏快照失败，尝试常规归档")
                        return False
                    sparse_result = result
                    repo_root = result.root
                    archive_bytes = 0
                    extract_warnings.extend(result.warnings)
                    _emit(
                        progress,
                        "extracting",
                        48,
                        f"稀疏快照获取 {result.files_written} 个文件（部分扫描）",
                    )
                    return True

                size_threshold = max(
                    self.settings.max_archive_bytes * 2,
                    100 * 1024 * 1024,
                )
                if repo.size_kb and repo.size_kb * 1024 > size_threshold:
                    try_sparse("仓库体积超过完整归档阈值")

                if repo_root is None:
                    _emit(progress, "downloading", 22, "流式下载仓库快照（按 commit SHA）")
                    try:
                        archive_path = download_archive(
                            client,
                            adapter,
                            parsed,
                            head.sha,
                            temp_dir,
                            max_bytes=self.settings.max_archive_bytes,
                            by_sha=True,
                        )
                        archive_bytes = archive_path.stat().st_size
                        _check_deadline(deadline)
                        _emit(progress, "extracting", 40, "安全解压并校验归档条目")
                        extracted = extract_archive(
                            archive_path,
                            temp_dir / "repo",
                            max_extracted_bytes=self.settings.max_extracted_bytes,
                            max_files=self.settings.max_files,
                        )
                        repo_root = extracted.root
                        extract_warnings.extend(extracted.warnings)
                        _emit(progress, "extracting", 48, f"已解压 {extracted.files_extracted} 个文件")
                    except ScanError as archive_error:
                        sparse_fallback_codes = {
                            "ARCHIVE_TOO_LARGE",
                            "TOO_MANY_FILES",
                            "ARCHIVE_INVALID",
                            "ARCHIVE_EMPTY",
                        }
                        if (
                            archive_error.code in sparse_fallback_codes
                            and try_sparse("归档超过体积/文件上限")
                        ):
                            pass
                        else:
                            clone_root, commit, archive_bytes, clone_warnings = self._clone_fallback(
                                parsed, chosen_branch, temp_dir, head, archive_error
                            )
                            repo_root = clone_root
                            extract_warnings.extend(clone_warnings)
                            _emit(progress, "extracting", 48, "归档失败，已使用 Git 克隆兜底")
                if repo_root is None:
                    raise ScanError(
                        "SPARSE_FAILED",
                        "无法获取仓库文件（归档与稀疏扫描均失败）",
                        http_status=502,
                    )
                _check_deadline(deadline)

                if commit.sha != head.sha:
                    report_id = make_report_id(parsed, chosen_branch, commit.sha)
                    cached = self._load_cached(report_id, force=force)
                    if cached is not None:
                        _emit(progress, "done", 100, "命中相同 commit 的缓存报告")
                        return cached

                _emit(progress, "indexing", 54, "建立文件索引并识别项目画像")
                index = build_file_index(
                    repo_root,
                    max_files=self.settings.max_files,
                    max_text_file_bytes=self.settings.max_text_file_bytes,
                    max_total_text_bytes=self.settings.max_total_text_bytes,
                )
                _check_deadline(deadline)
                ctx = AnalyzerContext(
                    parsed=parsed,
                    repo=repo,
                    commit=commit,
                    index=index,
                    adapter=adapter,
                )

                _emit(progress, "analyzing", 60, "检查 README 完整度")
                readme_out = analyze_readme(ctx)
                ctx.readme = readme_out.section
                _check_deadline(deadline)

                _emit(progress, "analyzing", 67, "检查依赖清单与锁文件")
                deps_out = analyze_dependencies(ctx)
                _check_deadline(deadline)

                _emit(progress, "analyzing", 73, "检查启动脚本与文档命令")
                startup_out = analyze_startup(ctx)
                _check_deadline(deadline)

                _emit(progress, "analyzing", 79, "盘点 Windows 专用脚本")
                windows_out = analyze_windows(ctx)
                _check_deadline(deadline)

                _emit(progress, "analyzing", 85, "扫描硬编码路径")
                paths_out = analyze_paths(ctx)
                _check_deadline(deadline)

                _emit(progress, "analyzing", 91, "扫描密钥与敏感信息")
                secrets_out = analyze_secrets(ctx)
                _check_deadline(deadline)

                all_risks = aggregate_risks(
                    [
                        *readme_out.risks,
                        *deps_out.risks,
                        *startup_out.risks,
                        *windows_out.risks,
                        *paths_out.risks,
                        *secrets_out.risks,
                    ]
                )

                _emit(progress, "scoring", 95, "计算五维评分与风险清单")
                identity = (
                    f"{parsed.platform}:{parsed.full_name.lower()}@{commit.sha}:"
                    f"{RULES_VERSION}:{SCHEMA_VERSION}"
                )
                score = build_score(
                    readme=readme_out,
                    dependencies=deps_out,
                    startup=startup_out,
                    windows=windows_out,
                    paths=paths_out,
                    secrets=secrets_out,
                    risks=all_risks,
                    identity=identity,
                )
                sections = ReportSections(
                    readme=readme_out.section,
                    dependencies=deps_out.section,
                    startup=startup_out.section,
                    windows=windows_out.section,
                    paths=paths_out.section,
                    secrets=secrets_out.section,
                )
                previous_entry = self.store.get_index_entry(
                    parsed.platform, repo.full_name, chosen_branch
                )
                update_info = UpdateInfo()
                if previous_entry and previous_entry.get("id") != report_id:
                    update_info = UpdateInfo(
                        previous_commit=previous_entry.get("commit_sha"),
                        previous_report_id=previous_entry.get("id"),
                        has_previous=True,
                    )
                ai_provider = self.settings.resolved_ai_provider()
                ai = AiAdvice(
                    status="not_generated" if ai_provider else "disabled",
                    provider=ai_provider,
                    model=self.settings.ai_model() if ai_provider else None,
                )
                warnings = [*extract_warnings, *index.warnings]
                if repo.archived:
                    warnings.append("仓库已归档（archived），上游可能不再维护")
                snapshot = SnapshotInfo(
                    compressed_bytes=archive_bytes,
                    extracted_bytes=sum(entry.size for entry in index.entries),
                    files_total=index.files_total,
                    files_scanned=len(index.entries),
                    files_skipped=index.files_skipped,
                    text_bytes_scanned=index.text_bytes_scanned,
                    truncated=index.truncated
                    or bool(sparse_result and sparse_result.truncated),
                    warnings=warnings[:20],
                )
                duration_ms = int((time.monotonic() - started) * 1000)
                report = Report(
                    id=report_id,
                    schema_version=SCHEMA_VERSION,
                    tool_version=TOOL_VERSION,
                    rules_version=RULES_VERSION,
                    platform=parsed.platform,
                    repo=repo,
                    commit=commit,
                    analyzed_at=utc_now_iso(),
                    duration_ms=duration_ms,
                    cached=False,
                    score=score,
                    sections=sections,
                    risks=all_risks,
                    suggestions=build_suggestions(all_risks, sections),
                    ai=ai,
                    update=update_info,
                    limits=snapshot,
                    project=index.project_info(),
                )
                _emit(progress, "saving", 98, "写入报告缓存与索引")
                self.store.save_report(report)
                _emit(progress, "done", 100, "体检完成")
                return report
        except ScanError:
            raise
        except Exception as exc:  # pragma: no cover - defensive wrapper
            logger.exception("Unexpected scan failure")
            raise ScanError(
                "SCAN_FAILED",
                "扫描过程中发生异常，请稍后重试",
                details=exc.__class__.__name__,
                http_status=500,
            ) from exc
        finally:
            if temp_dir is not None:
                safe_rmtree(temp_dir)
