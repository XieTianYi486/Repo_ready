from __future__ import annotations

from pathlib import Path

from backend.app.services.analyzers.secrets import analyze_secrets, _should_skip_generic
from backend.app.utils.secrets_patterns import mask_secret
from backend.tests.helpers import build_context, build_report, copy_demo_repo, make_repo


def run_secrets(root: Path):
    ctx = build_context(root)
    output = analyze_secrets(ctx)
    return ctx, output


def test_fixture_secrets_are_masked(tmp_path):
    root = copy_demo_repo(tmp_path)
    _, output = run_secrets(root)
    rule_ids = {finding.rule_id for finding in output.section.findings}
    assert "SEC-OPENAI-PROJ" in rule_ids
    assert "SEC-AWS" in rule_ids
    serialized = output.section.model_dump_json()
    assert "sk-proj-TESTONLY" not in serialized
    assert "AKIA1234567890ABCDEF" not in serialized
    assert "sk-p…" in serialized
    assert output.score == 0
    assert output.section.counts_by_severity.get("critical", 0) >= 2


def test_env_file_and_gitignore(tmp_path):
    root = copy_demo_repo(tmp_path)
    (root / ".env").write_text(
        "OPENAI_API_KEY=sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345\n"
        "DEBUG=true\n",
        encoding="utf-8",
    )
    _, output = run_secrets(root)
    assert ".env" in output.section.env_files
    env_findings = [
        finding for finding in output.section.findings if finding.rule_id == "SEC-ENV-FILE"
    ]
    assert env_findings and env_findings[0].severity == "critical"
    assert output.section.gitignore_env is False
    assert any(risk.rule_id == "SEC-GITIGNORE-ENV" for risk in output.risks)
    assert "sk-proj-ABCDEFGHIJ" not in output.section.model_dump_json()


def test_placeholders_ignored(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "src/app.py": (
                'API_KEY = "your-api-key-here"\n'
                'TOKEN = "example-token-value"\n'
                'AUTH = "Bearer <token>"\n'
                'AWS = "AKIAIOSFODNN7EXAMPLE"\n'
                'PASSWORD = "aaaaaaaabbbbbbbb"\n'
            )
        },
    )
    _, output = run_secrets(root)
    assert output.section.findings == []


def test_method_chain_not_generic_secret(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "src/UserService.java": (
                'String password = configService.selectConfigByKey("sys.user.initPassword");\n'
            )
        },
    )
    _, output = run_secrets(root)
    assert output.section.findings == []
    assert _should_skip_generic("configService.selectConfigByKey") is True
    assert _should_skip_generic("aB3xK9mQ2pL7vR4t") is False


def test_all_provider_patterns(tmp_path):
    secret_lines = [
        'anthropic = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"',
        'openai = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"',
        'aws = "AKIAABCDEFGHIJKLMNOP"',
        'aliyun = "LTAIAbcdefghijklmnop"',
        'tencent = "AKIDAbcdefghijklmnopqrst"',
        'github = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"',
        'gitlab = "glpat-ABCDEFGHIJKLMNOPQRST"',
        'slack = "xoxb-AbCdEfGhIjKl"',
        'google = "AIzaABCDEFGHIJKLMNOPQRSTUVWXYZ012345678"',
        # Split in source to avoid GitHub push-protection false positives;
        # the runtime value is still the fake test key.
        'stripe = "sk_' + 'live_' + 'ABCDEFGHIJKLMNOPQRSTUVWX"',
        'sendgrid = "SG.ABCDEFGHIJKLMNOP.QRSTUVWXYZ0123456789"',
        'bearer = "Bearer ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"',
        'jwt = "eyJABCDEFGHIJ.eyJABCDEFGHIJ.ABCDEFGHIJ"',
        "-----BEGIN RSA PRIVATE KEY-----",
        'azure = "AccountKey=ZYXWVUTSRQPONMLKJIHGFEDCBA987654"',
        "_authToken=ABCDEFGHIJKLMNOPQRSTUV",
    ]
    root = make_repo(tmp_path, {"src/leaks.py": "\n".join(secret_lines) + "\n"})
    _, output = run_secrets(root)
    ids = {finding.rule_id for finding in output.section.findings}
    expected = {
        "SEC-ANTHROPIC",
        "SEC-OPENAI-PROJ",
        "SEC-AWS",
        "SEC-ALIYUN",
        "SEC-TENCENT",
        "SEC-GITHUB",
        "SEC-GITLAB",
        "SEC-SLACK",
        "SEC-GOOGLE",
        "SEC-STRIPE",
        "SEC-SENDGRID",
        "SEC-BEARER",
        "SEC-JWT",
        "SEC-PRIVATE-KEY",
        "SEC-AZURE-ACCOUNT-KEY",
        "SEC-NPM-AUTH",
    }
    assert expected.issubset(ids)
    assert output.section.counts_by_severity.get("critical", 0) >= 5
    serialized = output.section.model_dump_json()
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" not in serialized


def test_docs_are_demoted(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "README.md": '# Demo\n\nkey = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"\n'
        },
    )
    _, output = run_secrets(root)
    finding = next(
        item for item in output.section.findings if item.rule_id == "SEC-ANTHROPIC"
    )
    assert finding.severity == "high"


def test_lockfiles_are_skipped(tmp_path):
    root = make_repo(
        tmp_path,
        {
            "package-lock.json": '{"key": "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"}',
        },
    )
    _, output = run_secrets(root)
    assert output.section.findings == []


def test_env_example_is_not_env_file(tmp_path):
    root = make_repo(
        tmp_path,
        {
            ".env.example": "API_KEY=your-key-here\n",
            ".gitignore": ".env\n",
            "app.py": "print('hello')\n",
        },
    )
    _, output = run_secrets(root)
    assert output.section.env_files == []
    assert output.section.gitignore_env is True


def test_mask_secret_never_returns_full_value():
    value = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    masked = mask_secret(value, "anthropic_key")
    assert masked.startswith("sk-a")
    assert masked.endswith("6789")
    assert value not in masked
    assert mask_secret(value, "private_key") == "[PRIVATE KEY REDACTED]"


def test_report_serialization_has_no_raw_secret(tmp_path):
    root = copy_demo_repo(tmp_path)
    report = build_report(root)
    serialized = report.model_dump_json()
    assert "sk-proj-TESTONLY000000000000000000" not in serialized
    assert "AKIA1234567890ABCDEF" not in serialized
