from __future__ import annotations

import json
from pathlib import Path

from epitaph import cli
from epitaph.describe import describe, render


def test_describe_is_deterministic_and_read_only(sample_repo: Path) -> None:
    before = sorted(path.relative_to(sample_repo).as_posix() for path in sample_repo.rglob("*"))

    description = describe(sample_repo)

    after = sorted(path.relative_to(sample_repo).as_posix() for path in sample_repo.rglob("*"))
    assert before == after
    assert description.facts["name"] == "sample"
    assert description.facts["totals"]["files"] >= 4
    assert description.prose is None
    assert description.used_llm is False
    assert "# sample" in description.markdown
    assert "<!-- epitaph:begin id=overview" in description.markdown


def test_describe_without_python_code_warns(tmp_path: Path) -> None:
    root = tmp_path / "vacia"
    root.mkdir()
    (root / "notas.txt").write_text("solo texto", encoding="utf-8")

    description = describe(root)

    assert description.facts["modules"] == []
    assert any("código fuente" in warning for warning in description.warnings)


def test_describe_render_smoke(sample_repo: Path, capsys) -> None:
    render(describe(sample_repo))
    output = capsys.readouterr().out
    assert "sample" in output
    assert "archivos" in output


def test_cli_describe_json(sample_repo: Path, capsys) -> None:
    code = cli.main(["--no-llm", "describe", str(sample_repo), "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "sample"
    assert payload["used_llm"] is False


def test_cli_describe_markdown_to_file(sample_repo: Path, tmp_path: Path) -> None:
    target = tmp_path / "salida.md"

    code = cli.main(["--no-llm", "describe", str(sample_repo), "--md", "--out", str(target)])

    assert code == 0
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert "<!-- epitaph:begin id=overview" in text


def test_cli_describe_rejects_missing_folder(tmp_path: Path) -> None:
    code = cli.main(["--no-llm", "describe", str(tmp_path / "no-existe")])

    assert code == 2
