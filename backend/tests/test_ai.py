from __future__ import annotations

import json

from backend.app.config import Settings
from backend.app.services.ai.base import AiError
from backend.app.services.ai.service import AiService
from backend.app.services.report_store import ReportStore
from backend.tests.helpers import build_report, copy_demo_repo


class FakeProvider:
    last_payload = None
    fail = False

    def __init__(self, settings):
        self.settings = settings
        self.model = "fake-model"

    def generate(self, payload, *, timeout):
        FakeProvider.last_payload = payload
        if FakeProvider.fail:
            raise AiError("fake failure", code="AI_FAKE")
        return (
            {
                "summary": "仓库可以接入，但需要先处理敏感信息。",
                "reference_score": 150,
                "score_reason": "存在凭据泄露，参考分低于主评分。",
                "blockers": [
                    {
                        "title": "轮换泄露的凭据",
                        "why": "假密钥触发了安全规则。",
                        "fix": "删除并轮换，清理历史。",
                        "severity": "high",
                    }
                ],
                "quick_wins": [{"action": "补充 .env.example", "effect": "降低配置成本"}],
                "integration_plan": [{"detail": "先修复安全问题"}, {"detail": "再补齐文档"}],
                "caveats": ["AI 结果仅供参考"],
            },
            "fake-model",
        )


def setup_service(tmp_path, *, enabled=True):
    FakeProvider.fail = False
    FakeProvider.last_payload = None
    settings = Settings(
        data_dir=tmp_path / "data",
        ai_enabled=enabled,
        ai_provider="anthropic",
        anthropic_api_key="test-key" if enabled else "",
        anthropic_model="fake-model",
    )
    store = ReportStore(settings.data_dir)
    report = build_report(copy_demo_repo(tmp_path))
    store.save_report(report)
    return settings, store, report, AiService(settings, store)


def test_ai_disabled_returns_disabled(tmp_path):
    _, _, report, service = setup_service(tmp_path, enabled=False)
    advice = service.generate(report.id)
    assert advice.status == "disabled"
    assert advice.reference_score is None


def test_ai_success_is_labeled_and_does_not_change_score(tmp_path, monkeypatch):
    _, store, report, service = setup_service(tmp_path)
    monkeypatch.setattr(
        "backend.app.services.ai.service.AnthropicProvider", FakeProvider
    )
    before = report.model_copy(deep=True)
    advice = service.generate(report.id)
    assert advice.status == "ready"
    assert advice.reference_score == 100  # clamped from 150
    assert advice.provider == "anthropic"
    assert advice.blockers[0].severity == "high"
    assert advice.integration_plan[0].step == 1

    loaded = store.load_report(report.id)
    assert loaded is not None
    assert loaded.ai.status == "ready"
    assert loaded.score.total == before.score.total
    assert loaded.score.fingerprint == before.score.fingerprint

    payload_text = json.dumps(FakeProvider.last_payload, ensure_ascii=False)
    assert "sk-proj-TESTONLY000000000000000000" not in payload_text
    assert "AKIA1234567890ABCDEF" not in payload_text


def test_ai_failure_does_not_change_score(tmp_path, monkeypatch):
    _, store, report, service = setup_service(tmp_path)
    FakeProvider.fail = True
    monkeypatch.setattr(
        "backend.app.services.ai.service.AnthropicProvider", FakeProvider
    )
    advice = service.generate(report.id)
    assert advice.status == "error"
    assert "fake failure" in (advice.error or "")
    loaded = store.load_report(report.id)
    assert loaded is not None
    assert loaded.score.fingerprint == report.score.fingerprint


def test_ai_normalizes_bad_severity(tmp_path, monkeypatch):
    class BadSeverityProvider(FakeProvider):
        def generate(self, payload, *, timeout):
            data, model = super().generate(payload, timeout=timeout)
            data["blockers"][0]["severity"] = "apocalyptic"
            return data, model

    _, _, report, service = setup_service(tmp_path)
    monkeypatch.setattr(
        "backend.app.services.ai.service.AnthropicProvider", BadSeverityProvider
    )
    advice = service.generate(report.id)
    assert advice.status == "ready"
    assert advice.blockers[0].severity == "medium"
