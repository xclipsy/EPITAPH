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

    # Entradas para _ask: opción 1 (directorio actual), opción 1 (on_autosave), modelo, permisos
    inputs = iter(["1", "1", "qwen2.5-coder:3b", "1"])
    monkeypatch.setattr(wizard, "_ask", lambda prompt, default, non_int: next(inputs, default))
    monkeypatch.setattr(wizard, "_yes", lambda prompt, default, non_int: True)

    res = wizard.run(tmp_path, non_interactive=False)
    assert res.root == tmp_path
    assert res.config.trigger.default == "on_autosave"
    assert res.config.project.name == tmp_path.name


def test_init_wizard_custom_workspace_option(tmp_path: Path, monkeypatch) -> None:
    from epitaph.ui import wizard

    custom_dir = tmp_path / "custom_proj"
    inputs = iter(["2", str(custom_dir), "2", "qwen2.5-coder:3b", "1"])
    monkeypatch.setattr(wizard, "_ask", lambda prompt, default, non_int: next(inputs, default))
    monkeypatch.setattr(wizard, "_yes", lambda prompt, default, non_int: True)

    res = wizard.run(tmp_path, non_interactive=False)
    assert res.root == custom_dir.resolve()
    assert res.config.trigger.default == "on_save"
    assert res.config.project.name == custom_dir.name
    assert (custom_dir / ".epitaph" / "config.toml").exists()


def test_resolve_root_uses_active_workspace(tmp_path: Path, monkeypatch) -> None:
    from epitaph.fs import set_active_workspace

    custom_ws = tmp_path / "saved_workspace"
    custom_ws.mkdir()
    (custom_ws / ".epitaph").mkdir()
    (custom_ws / ".epitaph" / "config.toml").write_text("[project]\nname = 'saved_ws'\n")

    # Mock global config file location to tmp_path
    global_file = tmp_path / "active_workspace.txt"
    monkeypatch.setattr("epitaph.fs.get_global_workspace_file", lambda: global_file)

    set_active_workspace(custom_ws)
    assert global_file.read_text(encoding="utf-8").strip() == str(custom_ws.resolve())

    # When no -C / --path argument is given, _resolve_root resolves to the active workspace
    resolved = cli._resolve_root(None)
    assert resolved == custom_ws.resolve()

    # When explicit path is given, it takes priority
    explicit_path = tmp_path / "explicit"
    explicit_path.mkdir()
    assert cli._resolve_root(str(explicit_path)) == explicit_path.resolve()


def test_cli_command_automatically_targets_saved_workspace(tmp_path: Path, monkeypatch, capsys) -> None:
    from epitaph.fs import set_active_workspace

    custom_ws = tmp_path / "auto_workspace"
    custom_ws.mkdir()
    (custom_ws / "src").mkdir()
    (custom_ws / "src" / "main.py").write_text("print('hello')\n")
    (custom_ws / ".epitaph").mkdir()
    (custom_ws / ".epitaph" / "config.toml").write_text("[project]\nname = 'auto_ws'\n")

    global_file = tmp_path / "global_active_ws.txt"
    monkeypatch.setattr("epitaph.fs.get_global_workspace_file", lambda: global_file)
    set_active_workspace(custom_ws)

    # Run cli analyze --json without passing -C
    code = cli.main(["analyze", "--json"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "auto_ws" in captured or "main.py" in captured


def test_chat_workspace_command(tmp_path: Path, monkeypatch) -> None:
    from epitaph.ui.chat import ChatSession

    ws1 = tmp_path / "ws1"
    ws1.mkdir()
    (ws1 / ".epitaph").mkdir()
    cfg1 = Config.load_or_default(ws1)
    cfg1.save(ws1)

    ws2 = tmp_path / "ws2"
    ws2.mkdir()
    (ws2 / ".epitaph").mkdir()
    cfg2 = Config.load_or_default(ws2)
    cfg2.save(ws2)

    global_file = tmp_path / "global_ws.txt"
    monkeypatch.setattr("epitaph.fs.get_global_workspace_file", lambda: global_file)

    session = ChatSession(ws1, cfg1)
    assert session.root == ws1.resolve()

    # Query workspace
    assert session.handle("/workspace") is True

    # Switch workspace
    assert session.handle(f"/workspace {ws2}") is True
    assert session.root == ws2.resolve()

