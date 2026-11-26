from __future__ import annotations

from backend.app.services.analyzers.dependencies import analyze_dependencies
from backend.tests.helpers import build_context, copy_demo_repo, make_repo


def test_demo_manifests(tmp_path):
    ctx = build_context(copy_demo_repo(tmp_path))
    output = analyze_dependencies(ctx)
    assert output.section.has_manifest is True
    assert "npm" in output.section.ecosystems
    assert "python" in output.section.ecosystems
    assert "package-lock.json" in output.section.lockfiles
    assert output.section.score == 100
    assert output.risks == []


def test_invalid_package_json(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "package.json": '{"name": "broken", ',
            "src/app.js": "console.log(1)\n",
        },
    )
    output = analyze_dependencies(build_context(root))
    manifest = output.section.manifests[0]
    assert manifest.parse_ok is False
    assert output.section.score <= 40
    assert any(risk.rule_id == "DEP-MANIFEST-INVALID" for risk in output.risks)
    assert output.risks[0].severity == "high"


def test_missing_manifest_with_code(tmp_path):
    root = make_repo(tmp_path, {"src/app.py": "print('hi')\n"})
    output = analyze_dependencies(build_context(root))
    assert output.section.has_manifest is False
    assert output.score == 0
    assert any(risk.rule_id == "DEP-MISSING-MANIFEST" for risk in output.risks)
    assert output.risks[0].severity == "high"


def test_pyproject_and_requirements(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "pyproject.toml": (
                "[project]\n"
                'name = "demo"\n'
                'dependencies = ["fastapi>=0.1", "httpx>=0.27"]\n'
            ),
            "requirements.txt": "flask==3.0.0\nrequests>=2.0\n",
            "app.py": "print('hi')\n",
        },
    )
    output = analyze_dependencies(build_context(root))
    assert output.section.has_manifest is True
    pyproject = next(
        manifest for manifest in output.section.manifests if manifest.path == "pyproject.toml"
    )
    assert pyproject.parse_ok is True
    assert pyproject.dependency_count == 2
    requirements = next(
        manifest
        for manifest in output.section.manifests
        if manifest.path == "requirements.txt"
    )
    assert requirements.dependency_count == 2
    assert output.section.score >= 70


def test_no_lockfile_risk(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "package.json": '{"scripts": {"dev": "vite"}, "dependencies": {"react": "19"}}',
            "src/app.js": "console.log(1)\n",
        },
    )
    output = analyze_dependencies(build_context(root))
    assert any(risk.rule_id == "DEP-NO-LOCKFILE" for risk in output.risks)
    assert output.section.score == 70
