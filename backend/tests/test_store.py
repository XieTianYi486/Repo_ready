from __future__ import annotations

from backend.app.services.report_store import ReportStore
from backend.app.utils.text import utc_now_iso
from backend.tests.helpers import build_report, copy_demo_repo


def test_save_load_and_index(tmp_path):
    store = ReportStore(tmp_path / "data")
    report = build_report(copy_demo_repo(tmp_path))
    store.save_report(report)
    loaded = store.load_report(report.id)
    assert loaded is not None
    assert loaded.id == report.id
    assert loaded.repo.full_name == "demo/demo-repo"
    recent = store.list_recent()
    assert recent and recent[0].id == report.id
    entry = store.get_index_entry("github", "demo/demo-repo", "main")
    assert entry and entry["id"] == report.id


def test_history_and_previous(tmp_path):
    store = ReportStore(tmp_path / "data")
    first = build_report(copy_demo_repo(tmp_path))
    store.save_report(first)
    second = first.model_copy(
        update={
            "id": "b" * 16,
            "commit": first.commit.model_copy(
                update={"sha": "b" * 40, "short_sha": "bbbbbbb"}
            ),
            "analyzed_at": utc_now_iso(),
        }
    )
    previous = store.previous_before(second)
    assert previous and previous["id"] == first.id
    store.save_report(second)
    entry = store.get_index_entry("github", "demo/demo-repo", "main")
    assert entry["id"] == second.id
    assert entry["history"][0]["id"] == first.id


def test_update_ai(tmp_path):
    store = ReportStore(tmp_path / "data")
    report = build_report(copy_demo_repo(tmp_path))
    store.save_report(report)
    updated = store.update_ai(report, report.ai.model_copy(update={"status": "ready", "summary": "ok"}))
    loaded = store.load_report(updated.id)
    assert loaded is not None
    assert loaded.ai.status == "ready"
    assert loaded.ai.summary == "ok"


def test_corrupt_report_is_quarantined(tmp_path):
    store = ReportStore(tmp_path / "data")
    report = build_report(copy_demo_repo(tmp_path))
    store.save_report(report)
    path = store.reports_dir / f"{report.id}.json"
    path.write_text("{not json", encoding="utf-8")
    assert store.load_report(report.id) is None
    assert (store.reports_dir / f"{report.id}.json.corrupt").exists()


def test_invalid_report_id_rejected(tmp_path):
    store = ReportStore(tmp_path / "data")
    assert store.load_report("../index") is None
    assert store.load_report("not-hex") is None
