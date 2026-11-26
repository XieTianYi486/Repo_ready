from __future__ import annotations

import json
import threading
import time
from typing import Literal

from fastapi import APIRouter, Query, Request, Response

from ..config import RULES_VERSION, TOOL_VERSION
from ..errors import ScanError
from ..models import (
    AiAdvice,
    AiHealth,
    ErrorResponse,
    HealthResponse,
    ReportSummary,
    ScanJobPublic,
    ScanRequest,
    ScanStartResponse,
    TokenHealth,
    UpdateCheckResponse,
)
from ..services.export import export_filename, render_markdown
from ..services.http_client import HttpClient
from ..services.platform.parser import parse_repo_url
from ..services.platform.registry import get_adapter

router = APIRouter(prefix="/api")

EXAMPLES = [
    {
        "url": "https://github.com/Plazmaz/leaky-repo",
        "label": "leaky-repo",
        "platform": "github",
        "highlight": "含假密钥：演示脱敏、封顶与风险排序",
    },
    {
        "url": "https://github.com/ChrisTitusTech/winutil",
        "label": "winutil",
        "platform": "github",
        "highlight": "PowerShell 脚本：演示 Windows 专用脚本盘点",
    },
    {
        "url": "https://github.com/sindresorhus/got",
        "label": "got",
        "platform": "github",
        "highlight": "规范 Node 项目：高分与完整接入路径样本",
    },
    {
        "url": "https://gitee.com/y_project/RuoYi",
        "label": "RuoYi",
        "platform": "gitee",
        "highlight": "Gitee 中文 Java 项目：验证双平台链路",
    },
    {
        "url": "https://github.com/octocat/Hello-World",
        "label": "Hello-World",
        "platform": "github",
        "highlight": "极简仓库：演示缺失项与低分",
    },
]


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    ai = settings.ai_public_config()
    return HealthResponse(
        status="ok",
        version=TOOL_VERSION,
        rules_version=RULES_VERSION,
        ai=AiHealth(**ai),
        tokens=TokenHealth(
            github=bool(settings.github_token),
            gitee=bool(settings.gitee_token),
        ),
    )


@router.get("/examples")
def examples() -> list[dict[str, str]]:
    return EXAMPLES


@router.post(
    "/scans",
    response_model=ScanStartResponse,
    responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
def start_scan(request: Request, payload: ScanRequest) -> ScanStartResponse:
    if len(payload.url or "") > 500:
        raise ScanError("INVALID_URL", "仓库链接过长", http_status=400)
    allowed, retry = request.app.state.scan_limiter.allow(_client_ip(request))
    if not allowed:
        raise ScanError(
            "RATE_LIMITED",
            f"操作过于频繁，请 {retry} 秒后重试",
            http_status=429,
            retry_after=retry,
        )
    parsed = parse_repo_url(payload.url, branch_override=payload.branch)
    job = request.app.state.scan_manager.submit(
        parsed,
        url=parsed.html_url,
        branch=parsed.branch,
        force=payload.force,
    )
    return ScanStartResponse(job_id=job.job_id, status=job.status)


@router.get("/scans/{job_id}", response_model=ScanJobPublic)
def get_scan(request: Request, job_id: str) -> ScanJobPublic:
    job = request.app.state.scan_manager.get(job_id)
    if job is None:
        raise ScanError("JOB_NOT_FOUND", "扫描任务不存在或已过期", http_status=404)
    return job


@router.get("/reports", response_model=list[ReportSummary])
def recent_reports(
    request: Request, limit: int = Query(10, ge=1, le=20)
) -> list[ReportSummary]:
    return request.app.state.report_store.list_recent(limit=limit)


def _load_report(request: Request, report_id: str):
    report = request.app.state.report_store.load_report(report_id)
    if report is None:
        raise ScanError("REPORT_NOT_FOUND", "报告不存在或已过期", http_status=404)
    return report


@router.get("/reports/{report_id}")
def get_report(request: Request, report_id: str):
    report = _load_report(request, report_id)
    return report


@router.post("/reports/{report_id}/refresh", response_model=ScanStartResponse)
def refresh_report(request: Request, report_id: str) -> ScanStartResponse:
    report = _load_report(request, report_id)
    allowed, retry = request.app.state.scan_limiter.allow(_client_ip(request))
    if not allowed:
        raise ScanError(
            "RATE_LIMITED",
            f"操作过于频繁，请 {retry} 秒后重试",
            http_status=429,
            retry_after=retry,
        )
    parsed = parse_repo_url(report.repo.html_url, branch_override=report.commit.branch)
    job = request.app.state.scan_manager.submit(
        parsed,
        url=report.repo.html_url,
        branch=report.commit.branch,
        force=True,
    )
    return ScanStartResponse(job_id=job.job_id, status=job.status)


@router.get("/reports/{report_id}/updates", response_model=UpdateCheckResponse)
def check_updates(request: Request, report_id: str) -> UpdateCheckResponse:
    report = _load_report(request, report_id)
    settings = request.app.state.settings
    cache = request.app.state.update_cache
    lock = request.app.state.update_cache_lock
    now = time.monotonic()
    with lock:
        cached = cache.get(report_id)
        if cached and cached[0] > now:
            return cached[1]

    parsed = parse_repo_url(report.repo.html_url, branch_override=report.commit.branch)
    adapter = get_adapter(
        report.platform,
        github_token=settings.github_token,
        gitee_token=settings.gitee_token,
    )
    try:
        with HttpClient(timeout_seconds=float(settings.request_timeout_seconds)) as client:
            head = adapter.fetch_head(client, parsed, report.commit.branch)
        if head.sha.lower() == report.commit.sha.lower():
            response = UpdateCheckResponse(
                status="up_to_date",
                current_commit=report.commit.sha,
                latest_commit=head.sha,
                latest_short=head.short_sha,
                message="报告基于分支最新 commit。",
            )
            ttl = settings.update_cache_seconds
        else:
            response = UpdateCheckResponse(
                status="update_available",
                current_commit=report.commit.sha,
                latest_commit=head.sha,
                latest_short=head.sha[:7],
                message=f"上游有新提交：{head.sha[:7]}，当前报告基于 {report.commit.short_sha}。",
            )
            ttl = settings.update_cache_seconds
    except ScanError as exc:
        response = UpdateCheckResponse(
            status="unknown",
            current_commit=report.commit.sha,
            message=f"暂时无法确认更新状态：{exc.message}",
            retry_after=exc.retry_after,
        )
        ttl = 60
    except Exception:
        response = UpdateCheckResponse(
            status="unknown",
            current_commit=report.commit.sha,
            message="暂时无法确认更新状态，已展示缓存报告。",
        )
        ttl = 60
    with lock:
        cache[report_id] = (time.monotonic() + ttl, response)
    return response


@router.post("/reports/{report_id}/ai", response_model=AiAdvice)
def generate_ai(request: Request, report_id: str) -> AiAdvice:
    allowed, retry = request.app.state.ai_limiter.allow(_client_ip(request))
    if not allowed:
        raise ScanError(
            "RATE_LIMITED",
            f"AI 请求过于频繁，请 {retry} 秒后重试",
            http_status=429,
            retry_after=retry,
        )
    _load_report(request, report_id)
    return request.app.state.ai_service.generate(report_id)


@router.get("/reports/{report_id}/export")
def export_report(
    request: Request,
    report_id: str,
    format: Literal["json", "md"] = Query("json"),
) -> Response:
    report = _load_report(request, report_id)
    filename = export_filename(report, "json" if format == "json" else "md")
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if format == "json":
        content = json.dumps(
            report.model_dump(mode="json"), ensure_ascii=False, indent=2
        )
        return Response(
            content=content,
            media_type="application/json; charset=utf-8",
            headers=headers,
        )
    content = render_markdown(report)
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers=headers,
    )
