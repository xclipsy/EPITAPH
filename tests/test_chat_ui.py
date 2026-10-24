from __future__ import annotations

from pathlib import Path

from epitaph.config import Config
from epitaph.llm.provider_ollama import OllamaProvider
from epitaph.ui.chat import ChatSession


def _session(root: Path) -> ChatSession:
    return ChatSession(root, Config.default(root.name))


def test_help_renders_a_command_catalog(sample_repo: Path, capsys) -> None:
    assert _session(sample_repo).handle("/help") is True

    output = capsys.readouterr().out
    assert "Catálogo de comandos" in output
    assert "/permissions" in output
    assert "Sintaxis / ejemplo" in output


def test_permissions_render_as_a_matrix(sample_repo: Path, capsys) -> None:
    assert _session(sample_repo).handle("/permissions") is True

    output = capsys.readouterr().out
    assert "Matriz de permisos" in output
    assert "write:readme" in output
    assert "write:code" in output


def test_natural_language_without_ollama_shows_a_hint(
    sample_repo: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: False)

    assert _session(sample_repo).handle("¿qué hace este proyecto?") is True

    output = capsys.readouterr().out
    assert "Ollama no está disponible" in output
    assert "ollama serve" in output


def test_tree_renders_project_hierarchy(sample_repo: Path, capsys) -> None:
    session = _session(sample_repo)
    assert session.handle("/tree") is True

    output = capsys.readouterr().out
    assert sample_repo.name in output


def test_metrics_renders_praxia_table(sample_repo: Path, capsys) -> None:
    session = _session(sample_repo)
    assert session.handle("/metrics") is True

    output = capsys.readouterr().out
    assert "Métricas Generales de Calidad" in output
    assert "Índice de Mantenibilidad" in output


def test_cycles_and_secrets_commands(sample_repo: Path, capsys) -> None:
    session = _session(sample_repo)
    assert session.handle("/cycles") is True
    out_cycles = capsys.readouterr().out
    assert "Dependencias Circulares" in out_cycles

    assert session.handle("/secrets") is True
    out_sec = capsys.readouterr().out
    assert "Secretos" in out_sec


def test_view_and_citation_shortcuts(sample_repo: Path, capsys) -> None:
    session = _session(sample_repo)
    test_file = sample_repo / "main.py"
    test_file.write_text("def hello():\n    print('hello world')\n", encoding="utf-8")

    assert session.handle("/view main.py") is True
    output = capsys.readouterr().out
    assert "main.py" in output

    # Test interactive citations
    session._render_interactive_citations("Consulta el archivo [main.py:1-2] para detalles.")
    assert "1" in session.citation_shortcuts
    assert session.handle("1") is True
    assert "main.py" in capsys.readouterr().out
