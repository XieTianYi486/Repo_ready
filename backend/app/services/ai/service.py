from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from ...config import Settings
from ...errors import ScanError
from ...models import AiAdvice, AiBlocker, AiQuickWin, AiStep, Report
from ...utils.secrets_patterns import (
    contains_high_confidence_secret,
    mask_secrets_in_line,
)
from ...utils.text import utc_now_iso
from ..report_store import ReportStore
from .anthropic_provider import AnthropicProvider
from .base import AiAdvicePayload, AiError
from .openai_provider import OpenAICompatibleProvider

logger = logging.getLogger(__name__)

SEVERITIES = {"critical", "high", "medium", "low", "info"}
MAX_PAYLOAD_CHARS = 9000


class AiService:
    def __init__(self, settings: Settings, store: ReportStore) -> None:
        self.settings = settings
        self.store = store
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def is_enabled(self) -> bool:
        return self.settings.resolved_ai_provider() is not None

    def _lock_for(self, report_id: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(report_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[report_id] = lock
            return lock

    def generate(self, report_id: str) -> AiAdvice:
        report = self.store.load_report(report_id)
        if report is None:
            raise ScanError("REPORT_NOT_FOUND", "报告不存在或已过期", http_status=404)
        if report.ai.status == "ready":
            return report.ai

        provider_name = self.settings.resolved_ai_provider()
        if provider_name is None:
            return AiAdvice(
                status="disabled",
                error="AI 未配置：请在 .env 中设置 AI_PROVIDER 以及对应的 API Key。",
            )

        lock = self._lock_for(report_id)
        with lock:
            report = self.store.load_report(report_id)
            if report is None:
                raise ScanError("REPORT_NOT_FOUND", "报告不存在或已过期", http_status=404)
            if report.ai.status == "ready":
                return report.ai
            started = time.monotonic()
            try:
                payload = self._build_payload(report)
                payload = self._sanitize(payload)
                payload = self._shrink(payload)
                serialized = json.dumps(payload, ensure_ascii=False)
                if contains_high_confidence_secret(serialized):
                    raise AiError(
                        "AI 请求脱敏自检未通过，已拒绝发送",
                        code="AI_REDACTION_FAILED",
                    )
                provider = (
                    AnthropicProvider(self.settings)
                    if provider_name == "anthropic"
                    else OpenAICompatibleProvider(self.settings)
                )
                data, model = provider.generate(
                    payload, timeout=self.settings.ai_timeout_seconds
                )
                advice = self._to_advice(
                    data,
                    provider=provider_name,
                    model=model,
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
                self.store.update_ai(report, advice)
                return advice
            except AiError as exc:
                advice = AiAdvice(
                    status="error",
                    provider=provider_name,
                    model=self.settings.ai_model(),
                    generated_at=utc_now_iso(),
                    latency_ms=int((time.monotonic() - started) * 1000),
                    error=exc.message,
                )
                self.store.update_ai(report, advice)
                return advice
            except Exception as exc:
                logger.exception("Unexpected AI failure")
                advice = AiAdvice(
                    status="error",
                    provider=provider_name,
                    model=self.settings.ai_model(),
                    generated_at=utc_now_iso(),
                    latency_ms=int((time.monotonic() - started) * 1000),
                    error=f"AI 建议生成失败（{exc.__class__.__name__}），可稍后重试",
                )
                self.store.update_ai(report, advice)
                return advice

    def _to_advice(
        self, data: dict[str, Any], *, provider: str, model: str, latency_ms: int
    ) -> AiAdvice:
        sanitized = self._normalize_advice_data(data)
        try:
            payload = AiAdvicePayload.model_validate(sanitized)
        except Exception as exc:
            raise AiError("AI 输出未通过结构校验，已丢弃", code="AI_INVALID_SCHEMA") from exc
        reference = payload.reference_score
        if isinstance(reference, bool) or not isinstance(reference, int):
            reference = None
        elif not 0 <= reference <= 100:
            reference = max(0, min(100, reference))
        return AiAdvice(
            status="ready",
            provider=provider,
            model=model,
            generated_at=utc_now_iso(),
            latency_ms=latency_ms,
            summary=(payload.summary or "")[:800],
            reference_score=reference,
            score_reason=(payload.score_reason or "")[:600],
            blockers=[
                AiBlocker(
                    title=item.title[:160],
                    why=item.why[:400],
                    fix=item.fix[:400],
                    severity=item.severity,
                )
                for item in payload.blockers[:6]
            ],
            quick_wins=[
                AiQuickWin(action=item.action[:300], effect=item.effect[:300])
                for item in payload.quick_wins[:6]
            ],
            integration_plan=[
                AiStep(step=index, detail=item.detail[:400])
                for index, item in enumerate(payload.integration_plan[:8], start=1)
            ],
            caveats=[item[:300] for item in payload.caveats[:6]],
        )

    def _normalize_advice_data(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise AiError("AI 返回的不是 JSON 对象", code="AI_INVALID_SCHEMA")
        summary = data.get("summary")
        score_reason = data.get("score_reason")
        reference = data.get("reference_score")
        if isinstance(reference, bool) or not isinstance(reference, (int, float)):
            reference = None
        elif reference is not None:
            reference = max(0, min(100, int(reference)))

        blockers: list[dict[str, Any]] = []
        raw_blockers = data.get("blockers")
        if isinstance(raw_blockers, list):
            for item in raw_blockers:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                why = str(item.get("why") or "").strip()
                fix = str(item.get("fix") or "").strip()
                if not title:
                    continue
                severity = str(item.get("severity") or "medium").lower()
                if severity not in SEVERITIES:
                    severity = "medium"
                blockers.append(
                    {"title": title, "why": why, "fix": fix, "severity": severity}
                )

        quick_wins: list[dict[str, Any]] = []
        raw_quick = data.get("quick_wins")
        if isinstance(raw_quick, list):
            for item in raw_quick:
                if not isinstance(item, dict):
                    continue
                action = str(item.get("action") or "").strip()
                effect = str(item.get("effect") or "").strip()
                if action:
                    quick_wins.append({"action": action, "effect": effect})

        plan: list[dict[str, Any]] = []
        raw_plan = data.get("integration_plan")
        if isinstance(raw_plan, list):
            for index, item in enumerate(raw_plan, start=1):
                if isinstance(item, dict):
                    detail = str(item.get("detail") or "").strip()
                else:
                    detail = str(item or "").strip()
                if detail:
                    plan.append({"step": index, "detail": detail})

        caveats: list[str] = []
        raw_caveats = data.get("caveats")
        if isinstance(raw_caveats, list):
            caveats = [str(item).strip() for item in raw_caveats if str(item).strip()]

        return {
            "summary": str(summary or ""),
            "reference_score": reference,
            "score_reason": str(score_reason or ""),
            "blockers": blockers,
            "quick_wins": quick_wins,
            "integration_plan": plan,
            "caveats": caveats,
        }

    def _build_payload(self, report: Report) -> dict[str, Any]:
        dimensions = [
            {
                "key": dimension.key,
                "name": dimension.name,
                "score": dimension.score,
                "weight": dimension.weight,
                "summary": dimension.summary[:180],
            }
            for dimension in report.score.dimensions
        ]
        risks = []
        for risk in report.risks[:10]:
            risks.append(
                {
                    "id": risk.id,
                    "severity": risk.severity,
                    "dimension": risk.dimension,
                    "title": risk.title[:160],
                    "file": risk.file,
                    "line": risk.line,
                    "evidence": (risk.evidence or "")[:160],
                    "recommendation": risk.recommendation[:240],
                }
            )
        sections = report.sections
        return {
            "repo": {
                "platform": report.platform,
                "full_name": report.repo.full_name,
                "description": (report.repo.description or "")[:300],
                "language": report.repo.language,
                "stars": report.repo.stars,
                "license": report.repo.license,
                "archived": report.repo.archived,
                "commit": report.commit.short_sha,
                "commit_message": (report.commit.message or "")[:200],
            },
            "score": {
                "total": report.score.total,
                "raw_total": report.score.raw_total,
                "grade": report.score.grade,
                "label": report.score.label,
                "caps": report.score.cap_reason,
                "dimensions": dimensions,
            },
            "risks": risks,
            "readme": {
                "present": sections.readme.present,
                "chars": sections.readme.chars,
                "sections": [
                    check.label for check in sections.readme.sections if check.present
                ],
                "missing": [
                    check.label for check in sections.readme.sections if not check.present
                ],
                "headings": sections.readme.headings[:8],
                "has_code_blocks": sections.readme.code_blocks > 0,
            },
            "dependencies": {
                "has_manifest": sections.dependencies.has_manifest,
                "ecosystems": sections.dependencies.ecosystems,
                "lockfiles": sections.dependencies.lockfiles[:6],
                "manifests": [
                    {
                        "path": item.path,
                        "kind": item.kind,
                        "parse_ok": item.parse_ok,
                        "dependency_count": item.dependency_count,
                    }
                    for item in sections.dependencies.manifests[:6]
                ],
            },
            "startup": {
                "suggested_command": sections.startup.suggested_command,
                "documented_commands": sections.startup.documented_commands[:6],
                "env_vars": sections.startup.env_vars[:15],
                "env_example": sections.startup.env_example,
                "entries": [
                    {
                        "source": entry.source,
                        "command": entry.command[:160],
                        "verified": entry.verified,
                    }
                    for entry in sections.startup.entries[:8]
                ],
            },
            "windows": {
                "count": sections.windows.count,
                "only_windows_start": sections.windows.only_windows_start,
                "files": [
                    {
                        "path": item.path,
                        "purpose": item.purpose,
                        "flags": item.flags,
                    }
                    for item in sections.windows.files[:6]
                ],
            },
            "paths": {
                "counts_by_rule": sections.paths.counts_by_rule,
                "counts_by_severity": sections.paths.counts_by_severity,
                "findings": [
                    {
                        "rule_id": item.rule_id,
                        "path": item.path,
                        "line": item.line,
                        "snippet": item.snippet[:140],
                        "severity": item.severity,
                    }
                    for item in sections.paths.findings[:6]
                ],
            },
            "secrets": {
                "counts_by_severity": sections.secrets.counts_by_severity,
                "env_files": sections.secrets.env_files[:6],
                "gitignore_env": sections.secrets.gitignore_env,
                "findings": [
                    {
                        "rule_id": item.rule_id,
                        "kind": item.kind,
                        "path": item.path,
                        "masked": item.masked,
                        "severity": item.severity,
                    }
                    for item in sections.secrets.findings[:6]
                ],
            },
        }

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, str):
            return mask_secrets_in_line(value, 500)
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: self._sanitize(item) for key, item in value.items()}
        return value

    def _shrink(self, payload: dict[str, Any]) -> dict[str, Any]:
        def size() -> int:
            return len(json.dumps(payload, ensure_ascii=False))

        while size() > MAX_PAYLOAD_CHARS and len(payload.get("risks", [])) > 3:
            payload["risks"].pop()
        while size() > MAX_PAYLOAD_CHARS and len(payload.get("paths", {}).get("findings", [])) > 0:
            payload["paths"]["findings"].pop()
        while size() > MAX_PAYLOAD_CHARS and len(payload.get("secrets", {}).get("findings", [])) > 0:
            payload["secrets"]["findings"].pop()
        while size() > MAX_PAYLOAD_CHARS and len(payload.get("readme", {}).get("headings", [])) > 0:
            payload["readme"]["headings"].pop()
        if size() > MAX_PAYLOAD_CHARS:
            encoded = json.dumps(payload, ensure_ascii=False)
            payload = {"trimmed": True, "excerpt": encoded[: MAX_PAYLOAD_CHARS - 200]}
        return payload
