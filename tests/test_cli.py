from __future__ import annotations

from pathlib import Path

from epitaph import cli
from epitaph.config import Config
from epitaph.llm.provider_ollama import OllamaProvider


def _prepare(root: Path) -> None:
    config = Config.default(root.name)
    config.permissions.write_readme = "allow"
    config.safety.require_clean_git = False
    config.save(root)


def _offline(monkeypatch) -> None:
    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: False)


def test_update_blocks_when_ollama_is_offline(
    sample_repo: Path, monkeypatch, capsys
) -> None:
    _prepare(sample_repo)
    _offline(monkeypatch)

    code = cli.main(["-C", str(sample_repo), "update", "--yes"])

    assert code == 3
    output = capsys.readouterr().out
    assert "OLLAMA NO DISPONIBLE" in output
    assert "ollama serve" in output


def test_update_blocks_when_there_are_no_models(
    sample_repo: Path, monkeypatch, capsys
) -> None:
    _prepare(sample_repo)
    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: True)
    monkeypatch.setattr(OllamaProvider, "list_models", lambda self: [])

    code = cli.main(["-C", str(sample_repo), "update", "--yes"])

    assert code == 3
    output = capsys.readouterr().out
    assert "SIN MODELOS LOCALES" in output
    assert "ollama pull qwen2.5-coder:3b" in output


def test_no_llm_bypasses_the_ollama_gate(
    sample_repo: Path, monkeypatch, capsys
) -> None:
    _prepare(sample_repo)
    _offline(monkeypatch)

    code = cli.main(["-C", str(sample_repo), "update", "--yes", "--no-llm"])

    assert code == 0
    assert "README actualizado" in capsys.readouterr().out


def test_chat_blocks_when_ollama_is_offline(
    sample_repo: Path, monkeypatch, capsys
) -> None:
    _prepare(sample_repo)
    _offline(monkeypatch)

    code = cli.main(["-C", str(sample_repo)])

    assert code == 3
    assert "OLLAMA NO DISPONIBLE" in capsys.readouterr().out


def test_doctor_still_runs_when_ollama_is_offline(
    sample_repo: Path, monkeypatch, capsys
) -> None:
    _prepare(sample_repo)
    _offline(monkeypatch)

    code = cli.main(["-C", str(sample_repo), "doctor"])

    assert code == 0
    assert "Diagnóstico de EPITAPH" in capsys.readouterr().out


def test_local_model_role_change_does_not_need_ollama(
    sample_repo: Path, monkeypatch
) -> None:
    _prepare(sample_repo)
    _offline(monkeypatch)

    code = cli.main(
        [
            "-C",
            str(sample_repo),
            "models",
            "role",
            "writer",
            "qwen2.5-coder:1.5b",
        ]
    )

    assert code == 0
    assert Config.load(sample_repo).llm.roles.writer == "qwen2.5-coder:1.5b"


def test_init_creates_configuration_and_state(tmp_path: Path, capsys) -> None:
    code = cli.main(["-C", str(tmp_path), "init"])
    assert code == 0

    config = Config.load(tmp_path)
    assert config.project.name == tmp_path.name
    assert (tmp_path / ".epitaph" / "config.toml").exists()
    assert (tmp_path / ".epitaph" / "state.json").exists()
    output = capsys.readouterr().out
    assert "Configuración completada" in output


def test_init_wizard_autosave_option(tmp_path: Path, monkeypatch) -> None:
    from epitaph.ui import wizard

    # Entradas para _ask: opción 1 (directorio actual), nombre de proyecto, opción 1 (on_autosave), modelo, permisos
    inputs = iter(["1", "MiProyecto", "1", "qwen2.5-coder:3b", "1"])
    monkeypatch.setattr(wizard, "_ask", lambda prompt, default, non_int: next(inputs, default))
    monkeypatch.setattr(wizard, "_yes", lambda prompt, default, non_int: True)

    res = wizard.run(tmp_path, non_interactive=False)
    assert res.root == tmp_path
    assert res.config.trigger.default == "on_autosave"
    assert res.config.project.name == "MiProyecto"


def test_init_wizard_custom_workspace_option(tmp_path: Path, monkeypatch) -> None:
    from epitaph.ui import wizard

    custom_dir = tmp_path / "custom_proj"
    inputs = iter(["2", str(custom_dir), "MiCustom", "2", "qwen2.5-coder:3b", "1"])
    monkeypatch.setattr(wizard, "_ask", lambda prompt, default, non_int: next(inputs, default))
    monkeypatch.setattr(wizard, "_yes", lambda prompt, default, non_int: True)

    res = wizard.run(tmp_path, non_interactive=False)
    assert res.root == custom_dir.resolve()
    assert res.config.trigger.default == "on_save"
    assert (custom_dir / ".epitaph" / "config.toml").exists()
