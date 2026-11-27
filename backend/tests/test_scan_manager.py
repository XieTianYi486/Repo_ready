from __future__ import annotations

import time

from backend.app.config import Settings
from backend.app.errors import ScanError
from backend.app.services.platform.parser import parse_repo_url
from backend.app.services.report_store import ReportStore
from backend.app.services.scan_manager import ScanManager


def test_rate_limit_retry_after_is_exposed(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path / "data")
    store = ReportStore(settings.data_dir)
    manager = ScanManager(settings, store)

    def fake_scan(*_args, **_kwargs):
        raise ScanError(
            "RATE_LIMITED",
            "平台限流",
            retry_after=42,
            http_status=429,
        )

    monkeypatch.setattr(manager.service, "scan", fake_scan)
    parsed = parse_repo_url("https://github.com/example/repo")
    job = manager.submit(parsed, url=parsed.html_url)
    current = None
    for _ in range(100):
        time.sleep(0.02)
        current = manager.get(job.job_id)
        if current and current.status == "failed":
            break
    manager.shutdown()

    assert current is not None
    assert current.status == "failed"
    assert current.error_code == "RATE_LIMITED"
    assert current.retry_after == 42
