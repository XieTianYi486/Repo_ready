from __future__ import annotations

from backend.app.services.scoring import WEIGHTS
from backend.tests.helpers import build_report, copy_demo_repo, make_repo


def test_demo_score_is_capped_by_critical_secret(tmp_path):
    report = build_report(copy_demo_repo(tmp_path))
    assert report.score.total == 49
    assert report.score.raw_total > report.score.total
    assert report.score.grade == "F"
    assert report.score.capped is True
    assert report.score.cap_reason
    assert report.score.dimensions[-1].key == "security"
    assert report.score.dimensions[-1].score == 0


def test_weights_sum_to_100():
    assert sum(WEIGHTS.values()) == 100


def test_fingerprint_is_stable(tmp_path):
    root = copy_demo_repo(tmp_path)
    first = build_report(root)
    second = build_report(root)
    assert first.score.fingerprint == second.score.fingerprint
    assert first.score.total == second.score.total
    assert first.score.dimensions == second.score.dimensions


def test_clean_repo_scores_high(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "README.md": """# Clean App

## Installation

```bash
npm install
```

## Usage

```bash
npm run dev
```

## Configuration

Set `PORT` if needed.

## Architecture

Simple app.

## License

MIT
""",
            "package.json": (
                '{"name":"clean","scripts":{"dev":"vite","build":"vite build"},'
                '"dependencies":{"react":"19.0.0"}}'
            ),
            "package-lock.json": '{"name":"clean","lockfileVersion":3,"packages":{}}',
            ".gitignore": ".env\nnode_modules/\n",
            "src/app.ts": "export const ok = true;\n",
        },
    )
    report = build_report(root)
    assert report.score.total >= 90
    assert report.score.grade in {"A", "B"}
    assert report.score.dimensions[0].score >= 70
    assert report.score.dimensions[4].score == 100


def test_dimension_risk_ids_are_valid(tmp_path):
    report = build_report(copy_demo_repo(tmp_path))
    risk_ids = {risk.id for risk in report.risks}
    for dimension in report.score.dimensions:
        assert set(dimension.risk_ids).issubset(risk_ids)
