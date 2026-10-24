from __future__ import annotations

from pathlib import Path

from epitaph.analyzers import analyze
from epitaph.config import Config
from epitaph.requirements import analyze as analyze_requirements


def test_cycles_are_detected(sample_repo: Path) -> None:
    facts = analyze(sample_repo, include_secrets=False)
    cycles = facts["cycles"]
    assert cycles, "se esperaba al menos un ciclo entre core y util"
    flat = {path for cycle in cycles for path in cycle}
    assert "src/app/core.py" in flat
    assert "src/app/util.py" in flat


def test_orphans_are_detected(sample_repo: Path) -> None:
    facts = analyze(sample_repo, include_secrets=False)
    assert "src/app/orphan.py" in facts["orphans"]
    assert "src/app/__main__.py" not in facts["orphans"]


def test_entrypoints_include_module_main(sample_repo: Path) -> None:
    facts = analyze(sample_repo, include_secrets=False)
    paths = {entry["path"] for entry in facts["entrypoints"]}
    assert "src/app/__main__.py" in paths


def test_internal_imports_are_not_external(sample_repo: Path) -> None:
    facts = analyze(sample_repo, include_secrets=False)
    external = set(facts["dependencies"]["python_imports"])
    assert "httpx" in external
    assert "yaml" in external
    assert "src" not in external
    assert "app" not in external


def test_requirements_missing_and_unused(sample_repo: Path) -> None:
    facts = analyze(sample_repo, include_secrets=False)
    config = Config.default("sample")
    result = analyze_requirements(sample_repo, facts, config)

    missing = {item["import"]: item["package"] for item in result["missing"]}
    assert missing.get("yaml") == "PyYAML"
    assert "httpx" not in missing
    assert any(line.startswith("rich") for line in result["unused"])


def test_declared_dependency_aliases_are_matched(tmp_path: Path) -> None:
    root = tmp_path / "aliases"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "mod.py").write_text("import yaml\n", encoding="utf-8")
    (root / "requirements.txt").write_text("PyYAML==6.0.1\n", encoding="utf-8")

    facts = analyze(root, include_secrets=False)
    config = Config.default("aliases")
    result = analyze_requirements(root, facts, config)
    assert result["missing"] == []


def test_stdlib_is_excluded(tmp_path: Path) -> None:
    root = tmp_path / "stdlib"
    root.mkdir()
    (root / "mod.py").write_text("import json\nimport os\nimport httpx\n", encoding="utf-8")
    facts = analyze(root, include_secrets=False)
    config = Config.default("stdlib")
    result = analyze_requirements(root, facts, config)
    names = {item["import"] for item in result["missing"]}
    assert names == {"httpx"}
