from __future__ import annotations

from pathlib import Path

from epitaph.analyzers import analyze
from epitaph.config import Config
from epitaph.requirements import analyze as analyze_requirements
from epitaph.requirements.suggest import build_suggested, render_diff, unified_diff


def test_suggested_file_lists_missing(sample_repo: Path) -> None:
    facts = analyze(sample_repo, include_secrets=False)
    config = Config.default("sample")
    result = analyze_requirements(sample_repo, facts, config)

    text = build_suggested(result)
    assert "PyYAML" in text
    assert "rich" in text  # declarada sin uso, comentada
    assert text.startswith("# Generado por EPITAPH")


def test_suggested_file_keeps_declared(sample_repo: Path) -> None:
    facts = analyze(sample_repo, include_secrets=False)
    config = Config.default("sample")
    result = analyze_requirements(sample_repo, facts, config)

    text = build_suggested(result)
    assert "httpx>=0.27" in text
    assert "PyYAML" in text


def test_suggested_file_without_changes(tmp_path: Path) -> None:
    root = tmp_path / "clean"
    root.mkdir()
    (root / "mod.py").write_text("import httpx\n", encoding="utf-8")
    (root / "requirements.txt").write_text("httpx>=0.27\n", encoding="utf-8")

    facts = analyze(root, include_secrets=False)
    config = Config.default("clean")
    result = analyze_requirements(root, facts, config)
    text = build_suggested(result)
    assert "Sin cambios" in text


def test_unified_diff_marks_additions() -> None:
    diff = unified_diff("httpx\n", "httpx\nPyYAML\n")
    assert "+PyYAML" in diff
    assert diff.startswith("---")


def test_render_diff_uses_configured_path(sample_repo: Path) -> None:
    facts = analyze(sample_repo, include_secrets=False)
    config = Config.default("sample")
    result = analyze_requirements(sample_repo, facts, config)
    diff = render_diff(sample_repo, config, result)
    assert "a/requirements.txt" in diff
    assert "b/requirements.txt" in diff


def test_ambiguous_alias_is_commented(tmp_path: Path) -> None:
    root = tmp_path / "ambiguous"
    root.mkdir()
    (root / "mod.py").write_text("import magic\n", encoding="utf-8")
    facts = analyze(root, include_secrets=False)
    config = Config.default("ambiguous")
    result = analyze_requirements(root, facts, config)

    text = build_suggested(result)
    assert "revisar: python-magic" in text
