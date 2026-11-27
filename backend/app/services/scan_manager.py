from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from ..config import Settings
from ..errors import ScanError
from ..models import JobStatus, ScanJobPublic
from ..utils.text import utc_now_iso
from .platform.parser import ParsedRepo
from .report_store import ReportStore
from .scan_service import ScanService

logger = logging.getLogger(__name__)

STAGE_LABELS = {
    "queued": "排队中",
    "validating": "解析仓库链接",
    "metadata": "获取仓库元数据",
    "downloading": "下载仓库快照",
    "extracting": "安全解压快照",
    "indexing": "建立文件索引",
    "analyzing": "执行六类检测",
    "scoring": "计算评分与风险",
    "saving": "写入报告缓存",
    "done": "体检完成",
    "failed": "体检失败",
}


@dataclass
class Job:
    id: str
    url: str
    status: JobStatus = "queued"
    stage: str = "queued"
    progress: int = 0
    message: str = ""
    report_id: str | None = None
    cached: bool = False
    error_code: str | None = None
    error_message: str | None = None
    retry_after: int | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    started_monotonic: float | None = None
    finished_monotonic: float | None = None

    def elapsed_ms(self) -> int:
        if self.started_monotonic is None:
            return 0
        end = self.finished_monotonic or time.monotonic()
        return max(0, int((end - self.started_monotonic) * 1000))


class ScanManager:
    def __init__(self, settings: Settings, store: ReportStore) -> None:
        self.settings = settings
        self.store = store
        self.service = ScanService(settings, store)
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, settings.scan_concurrency),
            thread_name_prefix="repoready-scan",
        )
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()
        self._active: dict[tuple[str, str, bool], str] = {}

    def submit(
        self,
        parsed: ParsedRepo,
        *,
        url: str,
        branch: str | None = None,
        force: bool = False,
    ) -> ScanJobPublic:
        key = (parsed.repo_key, (branch or "").strip(), bool(force))
        with self._lock:
            existing_id = self._active.get(key)
            if existing_id:
                existing = self._jobs.get(existing_id)
                if existing and existing.status in {"queued", "running"}:
                    return self._public(existing)
            job_id = uuid.uuid4().hex[:16]
            job = Job(id=job_id, url=url)
            self._jobs[job_id] = job
            self._active[key] = job_id
            self._prune_locked()
        self._executor.submit(self._run, job_id, parsed, branch, force, key)
        with self._lock:
            return self._public(self._jobs[job_id])

    def _run(
        self,
        job_id: str,
        parsed: ParsedRepo,
        branch: str | None,
        force: bool,
        active_key: tuple[str, str, bool],
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "running"
            job.stage = "validating"
            job.message = "开始扫描"
            job.progress = 2
            job.started_monotonic = time.monotonic()
            job.updated_at = utc_now_iso()

        def on_progress(stage: str, progress: int, message: str) -> None:
            with self._lock:
                current = self._jobs.get(job_id)
                if current is None:
                    return
                current.stage = stage
                current.progress = max(0, min(100, progress))
                current.message = message
                current.updated_at = utc_now_iso()

        try:
            report = self.service.scan(
                parsed,
                branch=branch,
                force=force,
                progress=on_progress,
            )
            with self._lock:
                current = self._jobs.get(job_id)
                if current is not None:
                    current.status = "succeeded"
                    current.stage = "done"
                    current.progress = 100
                    current.report_id = report.id
                    current.cached = report.cached
                    current.message = "命中缓存" if report.cached else "体检完成"
                    current.finished_monotonic = time.monotonic()
                    current.updated_at = utc_now_iso()
        except ScanError as exc:
            logger.info("Scan %s failed: %s %s", job_id, exc.code, exc.message)
            with self._lock:
                current = self._jobs.get(job_id)
                if current is not None:
                    current.status = "failed"
                    current.stage = "failed"
                    current.error_code = exc.code
                    current.error_message = exc.message
                    current.retry_after = exc.retry_after
                    current.message = exc.message
                    current.progress = min(current.progress, 99)
                    current.finished_monotonic = time.monotonic()
                    current.updated_at = utc_now_iso()
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected job failure")
            with self._lock:
                current = self._jobs.get(job_id)
                if current is not None:
                    current.status = "failed"
                    current.stage = "failed"
                    current.error_code = "SCAN_FAILED"
                    current.error_message = "扫描过程中发生异常，请稍后重试"
                    current.progress = min(current.progress, 99)
                    current.finished_monotonic = time.monotonic()
                    current.updated_at = utc_now_iso()
        finally:
            with self._lock:
                self._active.pop(active_key, None)

    def _public(self, job: Job) -> ScanJobPublic:
        return ScanJobPublic(
            job_id=job.id,
            status=job.status,
            stage=job.stage,
            stage_label=STAGE_LABELS.get(job.stage, job.stage),
            message=job.message,
            progress=job.progress,
            url=job.url,
            report_id=job.report_id,
            cached=job.cached,
            error_code=job.error_code,
            error_message=job.error_message,
            retry_after=job.retry_after,
            elapsed_ms=job.elapsed_ms(),
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    def get(self, job_id: str) -> ScanJobPublic | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._public(job) if job else None

    def _prune_locked(self) -> None:
        terminal = [
            job
            for job in self._jobs.values()
            if job.status in {"succeeded", "failed"}
        ]
        if len(terminal) <= 80:
            return
        terminal.sort(key=lambda item: item.updated_at)
        for job in terminal[: len(terminal) - 80]:
            self._jobs.pop(job.id, None)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
