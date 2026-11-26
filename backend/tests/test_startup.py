from __future__ import annotations

from backend.app.services.analyzers.readme import analyze_readme
from backend.app.services.analyzers.startup import analyze_startup
from backend.tests.helpers import build_context, copy_demo_repo, make_repo


def prepare_root(root):
    ctx = build_context(root)
    readme = analyze_readme(ctx)
    ctx.readme = readme.section
    return ctx, analyze_startup(ctx)


def test_demo_startup(tmp_path):
    ctx, output = prepare_root(copy_demo_repo(tmp_path))
    assert output.section.suggested_command == "npm run dev"
    assert output.section.score >= 80
    assert output.section.env_example is True
    assert "PORT" in output.section.env_vars
    assert output.risks == []


def test_shell_script_is_a_start_path(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "ry.sh": "#!/bin/sh\njava -jar target/app.jar\n",
            "pom.xml": "<project></project>",
        },
    )
    _, output = prepare_root(root)
    assert any(
        entry.source == "script" and entry.command == "./ry.sh"
        for entry in output.section.entries
    )
    assert output.section.suggested_command == "./ry.sh"
    assert output.section.score >= 40


def test_missing_start_path(tmp_path):
    root = make_repo(tmp_path, {"src/app.py": "print('hi')\n"})
    _, output = prepare_root(root)
    assert output.score == 0
    assert any(risk.rule_id == "START-MISSING" for risk in output.risks)
    assert output.risks[0].severity == "high"


def test_readme_command_mismatch(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "package.json": '{"scripts": {"dev": "vite"}}',
            "README.md": "# Demo\n\n## 使用\n\n```bash\nnpm run start\n```\n",
        },
    )
    _, output = prepare_root(root)
    assert output.section.mismatches
    assert any(risk.rule_id == "START-MISMATCH" for risk in output.risks)


def test_env_vars_without_example(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "app.py": (
                "import os\n"
                'db = os.environ.get("DATABASE_URL")\n'
                'port = os.getenv("PORT")\n'
            ),
            "README.md": "# Demo\n\n## Usage\n\n```bash\npython app.py\n```\n",
        },
    )
    _, output = prepare_root(root)
    assert "DATABASE_URL" in output.section.env_vars
    assert output.section.env_example is False
    assert any(risk.rule_id == "START-ENV-UNDOCUMENTED" for risk in output.risks)
