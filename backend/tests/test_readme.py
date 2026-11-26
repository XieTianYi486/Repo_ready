from __future__ import annotations

from backend.app.services.analyzers.readme import analyze_readme
from backend.tests.helpers import build_context, copy_demo_repo, make_repo


def test_demo_readme_is_complete(tmp_path):
    output = analyze_readme(build_context(copy_demo_repo(tmp_path)))
    assert output.section.present is True
    assert output.section.score == 100
    assert output.section.has_install and output.section.has_usage
    assert output.risks == []


def test_missing_readme(tmp_path):
    root = make_repo(tmp_path, {"src/app.py": "print('hi')\n"})
    output = analyze_readme(build_context(root))
    assert output.section.present is False
    assert output.score == 0
    assert output.risks[0].rule_id == "DOC-README-MISSING"
    assert output.risks[0].severity == "high"


def test_thin_readme(tmp_path):
    root = make_repo(tmp_path, {"README.md": "# Demo\n\nHello.\n"})
    output = analyze_readme(build_context(root))
    assert output.section.present is True
    assert output.score < 50
    assert any(risk.rule_id == "DOC-README-QUICKSTART" for risk in output.risks)


def test_placeholders_are_penalized(tmp_path):
    readme = """# your-project

## 安装

```bash
npm install
```

## 使用

```bash
npm run dev
```

## 配置

TODO: describe env.

## API

Architecture.

## License

MIT
"""
    root = make_repo(tmp_path, {"README.md": readme})
    output = analyze_readme(build_context(root))
    assert output.section.placeholders
    assert any(risk.rule_id == "DOC-README-PLACEHOLDER" for risk in output.risks)
    assert output.section.score < 100


def test_chinese_headings(tmp_path):
    readme = """# 项目

## 安装

```bash
pip install -r requirements.txt
```

## 使用

```bash
python app.py
```

## 配置

环境变量说明。

## 架构

目录说明。

## 许可证

MIT
"""
    root = make_repo(tmp_path, {"README.md": readme})
    output = analyze_readme(build_context(root))
    assert all(check.present for check in output.section.sections)
