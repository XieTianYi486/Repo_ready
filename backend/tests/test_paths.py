from __future__ import annotations

from backend.app.services.analyzers.paths import analyze_paths
from backend.tests.helpers import build_context, copy_demo_repo, make_repo


def run_paths(root):
    return analyze_paths(build_context(root))


def test_demo_fixture_paths(tmp_path):
    output = run_paths(copy_demo_repo(tmp_path))
    findings = output.section.findings
    assert any(
        finding.rule_id == "PATH-WIN-DRIVE"
        and finding.path == "src/config.js"
        and finding.severity == "high"
        for finding in findings
    )
    assert any(
        finding.rule_id == "PATH-MAC-HOME"
        and finding.path == "src/config.js"
        and finding.severity == "high"
        for finding in findings
    )
    assert any(
        finding.rule_id == "PATH-LINUX-HOME"
        and finding.path == "docs/guide.md"
        and finding.severity == "low"
        for finding in findings
    )
    assert not any("example.com" in finding.snippet for finding in findings)
    assert any("***" in finding.snippet for finding in findings)
    assert output.section.penalty > 0
    assert output.score < 100


def test_comment_paths_are_demoted(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "config/app.yml": (
                "# example: C:\\Users\\Alice\\app\n"
                "upload_path: C:\\Users\\Bob\\uploads\n"
            )
        },
    )
    output = run_paths(root)
    comment = next(
        finding
        for finding in output.section.findings
        if finding.line == 1 and finding.rule_id == "PATH-WIN-DRIVE"
    )
    active = next(
        finding
        for finding in output.section.findings
        if finding.line == 2 and finding.rule_id == "PATH-WIN-DRIVE"
    )
    assert comment.severity == "medium"
    assert active.severity == "high"


def test_placeholders_are_ignored(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "src/app.py": (
                'a = r"C:\\Users\\<user>\\app"\n'
                'b = "/home/username/app"\n'
                'c = "${HOME}/app"\n'
                'd = "C:\\\\path\\\\to\\\\file"\n'
            )
        },
    )
    output = run_paths(root)
    assert output.section.findings == []


def test_urls_are_ignored(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "src/app.js": (
                'const u = "https://example.com/home/alice/path";\n'
                'const v = "https://example.com/Users/alice/path";\n'
                'const w = "file:///C:/Users/alice/data";\n'
            )
        },
    )
    output = run_paths(root)
    snippets = [finding.snippet for finding in output.section.findings]
    assert not any("example.com" in snippet for snippet in snippets)
    assert any("file:///C:" in snippet or "C:/Users" in snippet for snippet in snippets)


def test_unc_and_forward_slash(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "scripts/setup.ps1": (
                '$share = "\\\\server\\share\\build"\n'
                '$drive = "D:/workspace/app"\n'
            )
        },
    )
    output = run_paths(root)
    rules = {finding.rule_id for finding in output.section.findings}
    assert "PATH-WIN-UNC" in rules
    assert "PATH-WIN-DRIVE" in rules


def test_non_code_pdm_is_demoted(tmp_path):
    root = make_repo(
        tmp_path,
        {"design/model.pdm": "path=C:\\Users\\Alice\\Desktop\\project\n"},
    )
    output = run_paths(root)
    finding = next(
        item for item in output.section.findings if item.rule_id == "PATH-WIN-DRIVE"
    )
    assert finding.severity == "low"
