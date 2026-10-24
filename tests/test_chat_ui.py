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
