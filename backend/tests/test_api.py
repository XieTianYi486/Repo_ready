from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.models import ScanJobPublic
from backend.app.utils.text import utc_now_iso
from backend.tests.helpers import build_report, copy_demo_repo


def make_settings(tmp_path: Path, *, with_dist: bool = False) -> Settings:
    dist = tmp_path / "dist"
    if with_dist:
        (dist / "assets").mkdir(parents=True, exist_ok=True)
        (dist / "index.html").write_text(
            "<!doctype html><div id='root'>SPA_OK</div>", encoding="utf-8"
        )
        (dist / "assets" / "app.js").write_text("console.log('asset')", encoding="utf-8")
    return Settings(
        data_dir=tmp_path / "data",
        frontend_dist=dist,
        ai_enabled=False,
        rate_limit_per_minute=100,
    )


class FakeManager:
    def submit(self, parsed, *, url, branch=None, force=False):
        now = utc_now_iso()
        return ScanJobPublic(
            job_id="job-test-1",
            status="queued",
            stage="queued",
            stage_label="排队中",
            message="",
            progress=0,
            url=url,
            created_at=now,
            updated_at=now,
        )

    def get(self, job_id):
        return None

    def shutdown(self):
        pass


def test_health_examples_and_reports(tmp_path):
    app = create_app(make_settings(tmp_path))
    report = build_report(copy_demo_repo(tmp_path))
    app.state.report_store.save_report(report)

    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["ai"]["enabled"] is False
        assert health.json()["tokens"] == {"github": False, "gitee": False}

        examples = client.get("/api/examples")
        assert examples.status_code == 200
        assert any(item["platform"] == "gitee" for item in examples.json())

        recent = client.get("/api/reports?limit=10")
        assert recent.status_code == 200
        assert recent.json()[0]["id"] == report.id

        detail = client.get(f"/api/reports/{report.id}")
        assert detail.status_code == 200
        assert detail.json()["repo"]["full_name"] == "demo/demo-repo"

        missing = client.get("/api/reports/ffffffffffffffff")
        assert missing.status_code == 404
        assert missing.json()["error_code"] == "REPORT_NOT_FOUND"

        job = client.get("/api/scans/nope")
        assert job.status_code == 404
        assert job.json()["error_code"] == "JOB_NOT_FOUND"

        api_404 = client.get("/api/does-not-exist")
        assert api_404.status_code == 404
        assert api_404.headers["content-type"].startswith("application/json")

        ai = client.post(f"/api/reports/{report.id}/ai")
        assert ai.status_code == 200
        assert ai.json()["status"] in {"disabled", "error"}


def test_exports(tmp_path):
    app = create_app(make_settings(tmp_path))
    report = build_report(copy_demo_repo(tmp_path))
    app.state.report_store.save_report(report)
    with TestClient(app) as client:
        markdown = client.get(f"/api/reports/{report.id}/export?format=md")
        assert markdown.status_code == 200
        assert "RepoReady 体检报告" in markdown.text
        assert "attachment" in markdown.headers["content-disposition"]

        payload = client.get(f"/api/reports/{report.id}/export?format=json")
        assert payload.status_code == 200
        data = json.loads(payload.content)
        assert data["repo"]["full_name"] == "demo/demo-repo"
        assert "sk-proj-TESTONLY" not in payload.text


def test_invalid_scan_urls(tmp_path):
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        response = client.post("/api/scans", json={"url": "https://evil.com/a/b"})
        assert response.status_code == 400
        assert response.json()["error_code"] == "UNSUPPORTED_PLATFORM"

        response = client.post("/api/scans", json={"url": ""})
        assert response.status_code == 400


def test_scan_submission_with_fake_manager(tmp_path):
    app = create_app(make_settings(tmp_path))
    app.state.scan_manager = FakeManager()
    with TestClient(app) as client:
        response = client.post(
            "/api/scans",
            json={"url": "https://github.com/octocat/Hello-World"},
        )
        assert response.status_code == 200
        assert response.json()["job_id"] == "job-test-1"
        assert response.json()["status"] == "queued"


def test_spa_fallback_and_assets(tmp_path):
    app = create_app(make_settings(tmp_path, with_dist=True))
    with TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "SPA_OK" in home.text

        route = client.get("/report/abc")
        assert route.status_code == 200
        assert "SPA_OK" in route.text

        asset = client.get("/assets/app.js")
        assert asset.status_code == 200
        assert "console.log" in asset.text

        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.headers["content-type"].startswith("application/json")


def test_spa_without_build_returns_help(tmp_path):
    app = create_app(make_settings(tmp_path, with_dist=False))
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 503
        assert "前端尚未构建" in response.text
