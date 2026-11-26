from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from pydantic import ValidationError

from ..models import AiAdvice, Report, ReportSummary
from ..utils.fs import atomic_write_json

REPORT_ID_RE = re.compile(r"^[a-f0-9]{16}$")
INDEX_VERSION = 1


class ReportStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.reports_dir = data_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = data_dir / "index.json"
        self._lock = threading.RLock()
        self._index: dict = self._load_index()

    def _empty_index(self) -> dict:
        return {"version": INDEX_VERSION, "repos": {}}

    def _load_index(self) -> dict:
        with self._lock:
            if self.index_path.exists():
                try:
                    payload = json.loads(self.index_path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict) and isinstance(payload.get("repos"), dict):
                        return payload
                except (OSError, ValueError):
                    pass
            rebuilt = self._rebuild_index()
            self._write_index(rebuilt)
            return rebuilt

    def _rebuild_index(self) -> dict:
        index = self._empty_index()
        reports: list[Report] = []
        for path in sorted(self.reports_dir.glob("*.json")):
            try:
                report = Report.model_validate(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            except (OSError, ValueError, ValidationError):
                continue
            reports.append(report)
        reports.sort(key=lambda item: item.analyzed_at)
        for report in reports:
            self._index_report(index, report, add_history=False)
        return index

    def _write_index(self, index: dict) -> None:
        atomic_write_json(self.index_path, index)

    def _repo_key(self, report: Report) -> str:
        return (
            f"{report.platform}:{report.repo.full_name.lower()}:"
            f"{report.commit.branch}"
        )

    def _summary_from_report(self, report: Report) -> dict:
        return {
            "id": report.id,
            "commit_sha": report.commit.sha,
            "commit_short": report.commit.short_sha,
            "total": report.score.total,
            "grade": report.score.grade,
            "analyzed_at": report.analyzed_at,
        }

    def _index_report(self, index: dict, report: Report, *, add_history: bool = True) -> None:
        repos = index.setdefault("repos", {})
        key = self._repo_key(report)
        existing = repos.get(key) or {}
        history = existing.get("history") or []
        if add_history and existing.get("id") and existing.get("id") != report.id:
            compact = {
                "id": existing.get("id"),
                "commit_sha": existing.get("commit_sha"),
                "commit_short": existing.get("commit_short"),
                "total": existing.get("total"),
                "grade": existing.get("grade"),
                "analyzed_at": existing.get("analyzed_at"),
            }
            history = [compact, *history][:10]
        repos[key] = {
            "id": report.id,
            "platform": report.platform,
            "full_name": report.repo.full_name,
            "branch": report.commit.branch,
            "commit_sha": report.commit.sha,
            "commit_short": report.commit.short_sha,
            "total": report.score.total,
            "grade": report.score.grade,
            "analyzed_at": report.analyzed_at,
            "history": history,
        }

    def save_report(self, report: Report, *, update_index: bool = True) -> None:
        path = self.reports_dir / f"{report.id}.json"
        payload = report.model_dump(mode="json")
        with self._lock:
            atomic_write_json(path, payload)
            if update_index:
                self._index_report(self._index, report)
                self._write_index(self._index)

    def load_report(self, report_id: str) -> Report | None:
        if not REPORT_ID_RE.match(report_id or ""):
            return None
        path = self.reports_dir / f"{report_id}.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return Report.model_validate(payload)
        except (OSError, ValueError, ValidationError):
            try:
                path.replace(path.with_suffix(".json.corrupt"))
            except OSError:
                pass
            return None

    def update_ai(self, report: Report, ai: AiAdvice) -> Report:
        updated = report.model_copy(update={"ai": ai})
        self.save_report(updated, update_index=False)
        return updated

    def get_index_entry(self, platform: str, full_name: str, branch: str) -> dict | None:
        with self._lock:
            key = f"{platform}:{full_name.lower()}:{branch}"
            entry = self._index.get("repos", {}).get(key)
            return dict(entry) if entry else None

    def previous_before(self, report: Report) -> dict | None:
        entry = self.get_index_entry(
            report.platform, report.repo.full_name, report.commit.branch
        )
        if not entry:
            return None
        if entry.get("id") == report.id:
            return None
        return entry

    def list_recent(self, limit: int = 10) -> list[ReportSummary]:
        with self._lock:
            entries = list(self._index.get("repos", {}).values())
        entries.sort(key=lambda item: item.get("analyzed_at", ""), reverse=True)
        summaries: list[ReportSummary] = []
        seen: set[str] = set()
        for entry in entries:
            report_id = entry.get("id")
            if not report_id or report_id in seen:
                continue
            seen.add(report_id)
            summaries.append(
                ReportSummary(
                    id=report_id,
                    platform=entry.get("platform", "github"),
                    full_name=entry.get("full_name", ""),
                    branch=entry.get("branch", ""),
                    commit_short_sha=entry.get("commit_short", ""),
                    total=int(entry.get("total", 0)),
                    grade=str(entry.get("grade", "F")),
                    analyzed_at=entry.get("analyzed_at", ""),
                    cached=False,
                )
            )
            if len(summaries) >= limit:
                break
        return summaries

    def list_history(self, platform: str, full_name: str, branch: str) -> list[dict]:
        entry = self.get_index_entry(platform, full_name, branch)
        if not entry:
            return []
        return list(entry.get("history") or [])
