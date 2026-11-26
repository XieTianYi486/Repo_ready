from __future__ import annotations

import json
import math

from ..config import FORMULA_VERSION, RULES_VERSION
from ..models import (
    DIMENSION_ORDER,
    SEVERITY_ORDER,
    DimensionScore,
    DimensionKey,
    Risk,
    ScoreInfo,
)
from ..utils.text import sha256_short
from .analyzers.context import AnalyzerOutput

WEIGHTS: dict[DimensionKey, int] = {
    "readme": 20,
    "dependencies": 15,
    "startup": 20,
    "cross_platform": 15,
    "security": 30,
}
DIMENSION_NAMES: dict[DimensionKey, str] = {
    "readme": "文档可读性",
    "dependencies": "依赖可安装性",
    "startup": "启动可运行性",
    "cross_platform": "跨平台接入性",
    "security": "安全合规性",
}


def round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def _status(score: int) -> str:
    if score >= 85:
        return "优秀"
    if score >= 70:
        return "良好"
    if score >= 50:
        return "待改进"
    return "风险"


def _grade(total: int) -> tuple[str, str]:
    if total >= 90:
        return "A", "可直接接入"
    if total >= 80:
        return "B", "小修后可接入"
    if total >= 70:
        return "C", "需治理后接入"
    if total >= 60:
        return "D", "风险较高，先整改"
    return "F", "存在阻断项，暂不建议接入"


def aggregate_risks(risks: list[Risk]) -> list[Risk]:
    by_id: dict[str, Risk] = {}
    for risk in risks:
        existing = by_id.get(risk.id)
        if existing is None or risk.occurrences > existing.occurrences:
            by_id[risk.id] = risk
    ordered = sorted(
        by_id.values(),
        key=lambda risk: (
            0 if risk.blocking else 1,
            SEVERITY_ORDER.get(risk.severity, 9),
            DIMENSION_ORDER.get(risk.dimension, 9),
            (risk.file or "").lower(),
            risk.line or 0,
            risk.title,
        ),
    )
    return ordered[:60]


def build_score(
    *,
    readme: AnalyzerOutput,
    dependencies: AnalyzerOutput,
    startup: AnalyzerOutput,
    windows: AnalyzerOutput,
    paths: AnalyzerOutput,
    secrets: AnalyzerOutput,
    risks: list[Risk],
    identity: str,
) -> ScoreInfo:
    windows_section = windows.section
    paths_section = paths.section
    windows_penalty = int(getattr(windows_section, "penalty", 0) or 0)
    paths_penalty = int(getattr(paths_section, "penalty", 0) or 0)
    cross_score = max(0, 100 - windows_penalty - paths_penalty)

    dimension_inputs: dict[DimensionKey, tuple[int, str, list[str]]] = {
        "readme": (readme.score, readme.section.summary, readme.reasons),
        "dependencies": (
            dependencies.score,
            dependencies.section.summary,
            dependencies.reasons,
        ),
        "startup": (startup.score, startup.section.summary, startup.reasons),
        "cross_platform": (
            cross_score,
            f"Windows 脚本扣分 -{windows_penalty}，硬编码路径扣分 -{paths_penalty}。",
            windows.reasons + paths.reasons,
        ),
        "security": (secrets.score, secrets.section.summary, secrets.reasons),
    }

    risks_by_dimension: dict[str, list[str]] = {}
    for risk in risks:
        risks_by_dimension.setdefault(risk.dimension, []).append(risk.id)

    dimensions: list[DimensionScore] = []
    weighted_sum = 0.0
    for key in ("readme", "dependencies", "startup", "cross_platform", "security"):
        score, summary, reasons = dimension_inputs[key]  # type: ignore[index]
        weight = WEIGHTS[key]  # type: ignore[index]
        weighted = round(score * weight / 100.0, 1)
        weighted_sum += weighted
        dimensions.append(
            DimensionScore(
                key=key,  # type: ignore[arg-type]
                name=DIMENSION_NAMES[key],  # type: ignore[index]
                score=int(max(0, min(100, score))),
                weight=weight,
                weighted=weighted,
                status=_status(score),
                summary=summary or "",
                reasons=reasons,
                risk_ids=sorted(set(risks_by_dimension.get(key, []))),
            )
        )

    raw_total = round_half_up(weighted_sum)
    caps_applied: list[str] = []
    severity_counts = getattr(secrets.section, "counts_by_severity", {}) or {}
    if severity_counts.get("critical", 0) > 0:
        caps_applied.append("检测到 critical 级密钥/私钥泄露：总分封顶 49（F）")
    elif severity_counts.get("high", 0) > 0:
        caps_applied.append("检测到 high 级敏感信息：总分封顶 69（D）")

    total = raw_total
    if severity_counts.get("critical", 0) > 0:
        total = min(total, 49)
    elif severity_counts.get("high", 0) > 0:
        total = min(total, 69)
    total = max(0, min(100, total))
    grade, label = _grade(total)

    fingerprint_payload = {
        "identity": identity,
        "rules_version": RULES_VERSION,
        "formula_version": FORMULA_VERSION,
        "dimensions": {
            dimension.key: {
                "score": dimension.score,
                "weight": dimension.weight,
            }
            for dimension in dimensions
        },
        "risks": sorted(
            f"{risk.id}:{risk.severity}:{risk.occurrences}" for risk in risks
        ),
    }
    fingerprint = sha256_short(
        json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True),
        16,
    )

    return ScoreInfo(
        total=total,
        raw_total=raw_total,
        grade=grade,  # type: ignore[arg-type]
        label=label,
        capped=bool(caps_applied),
        cap_reason=caps_applied,
        dimensions=dimensions,
        formula_version=FORMULA_VERSION,
        fingerprint=fingerprint,
    )
