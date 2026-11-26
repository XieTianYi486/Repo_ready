from __future__ import annotations

from backend.app.services.analyzers.readme import analyze_readme
from backend.app.services.analyzers.startup import analyze_startup
from backend.app.services.analyzers.windows_scripts import analyze_windows
from backend.tests.helpers import build_context, copy_demo_repo, make_repo


def prepare_root(root):
    ctx = build_context(root)
    readme = analyze_readme(ctx)
    ctx.readme = readme.section
    analyze_startup(ctx)
    return analyze_windows(ctx)


def test_demo_windows_scripts(tmp_path):
    output = prepare_root(copy_demo_repo(tmp_path))
    assert output.section.count == 2
    deploy = next(
        item for item in output.section.files if item.path.endswith("deploy.ps1")
    )
    assert deploy.purpose == "deploy"
    assert "download_execute" in deploy.flags
    assert "run_as_admin" in deploy.flags
    assert deploy.severity == "medium"
    assert output.section.only_windows_start is False
    assert any(risk.rule_id == "WIN-RISKY-SCRIPT" for risk in output.risks)
    assert output.section.penalty > 0


def test_only_windows_start(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "start.bat": "@echo off\ncd /d C:\\app\npython app.py\n",
            "app.py": "print('hi')\n",
        },
    )
    output = prepare_root(root)
    assert output.section.only_windows_start is True
    assert any(risk.rule_id == "WIN-ONLY-START" for risk in output.risks)


def test_no_windows_scripts(tmp_path):
    root = make_repo(tmp_path, {"src/app.py": "print('hi')\n"})
    output = prepare_root(root)
    assert output.section.count == 0
    assert output.section.penalty == 0
    assert output.risks == []
