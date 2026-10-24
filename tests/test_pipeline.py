from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from epitaph import pipeline
from epitaph.config import Config
from epitaph.errors import DirtyWorkTree, PermissionDenied
from epitaph.state import State


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _config(root: Path) -> Config:
    config = Config.default(root.name)
    config.permissions.write_readme = "allow"
    config.safety.require_clean_git = False
    return config


def test_dry_run_does_not_write(sample_repo: Path) -> None:
    config = _config(sample_repo)
    before = (sample_repo / "README.md").read_text(encoding="utf-8")

    result = pipeline.update(
        sample_repo, config, State(), use_llm=False, dry_run=True
    )

    assert result.merge is not None
    assert result.merge.changed is True
    assert result.written is False
    assert result.skipped_reason == "dry-run"
    assert (sample_repo / "README.md").read_text(encoding="utf-8") == before
    assert not (sample_repo / "suggestions.md").exists()


def test_write_preserves_human_text(sample_repo: Path) -> None:
    config = _config(sample_repo)
    result = pipeline.update(sample_repo, config, State(), use_llm=False)

    assert result.written is True
    text = (sample_repo / "README.md").read_text(encoding="utf-8")
    assert "Texto humano que debe sobrevivir." in text
    assert "Esto no lo escribe EPITAPH." in text
    assert "<!-- epitaph:begin id=overview" in text
    assert (sample_repo / "suggestions.md").exists()
    assert (sample_repo / ".epitaph" / "audit.log").exists()


def test_second_run_is_idempotent(sample_repo: Path) -> None:
    config = _config(sample_repo)
    pipeline.update(sample_repo, config, State(), use_llm=False)
    after_first = (sample_repo / "README.md").read_text(encoding="utf-8")

    second = pipeline.update(sample_repo, config, State(), use_llm=False)

    assert second.merge is not None
    assert second.merge.changed is False
    assert second.written is False
    assert second.skipped_reason == "sin cambios"
    assert (sample_repo / "README.md").read_text(encoding="utf-8") == after_first


def test_permission_denied_blocks_write(sample_repo: Path) -> None:
    config = _config(sample_repo)
    config.permissions.write_readme = "deny"
    before = (sample_repo / "README.md").read_text(encoding="utf-8")

    with pytest.raises(PermissionDenied):
        pipeline.update(sample_repo, config, State(), use_llm=False)

    assert (sample_repo / "README.md").read_text(encoding="utf-8") == before


def test_ask_requires_approval(sample_repo: Path) -> None:
    config = _config(sample_repo)
    config.permissions.write_readme = "ask"

    with pytest.raises(PermissionDenied):
        pipeline.update(sample_repo, config, State(), use_llm=False)

    result = pipeline.update(
        sample_repo, config, State(), use_llm=False, auto_approve=True
    )
    assert result.written is True


def test_dirty_git_blocks_write(sample_repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=sample_repo, check=True, capture_output=True)
    config = _config(sample_repo)
    config.safety.require_clean_git = True

    with pytest.raises(DirtyWorkTree):
        pipeline.update(sample_repo, config, State(), use_llm=False)


def test_init_artifacts_do_not_block_first_update(sample_repo: Path) -> None:
    from epitaph.preferences import PreferenceStore

    _git(sample_repo, "init")
    _git(sample_repo, "config", "user.email", "test@example.com")
    _git(sample_repo, "config", "user.name", "Test")
    _git(sample_repo, "add", "-A")
    _git(sample_repo, "commit", "-m", "base")

    config = _config(sample_repo)
    config.safety.require_clean_git = True
    config.permissions.write_readme = "allow"
    PreferenceStore.for_root(sample_repo).add("readme.tone", "directo")

    result = pipeline.update(sample_repo, config, State(), use_llm=False)

    assert result.written is True


def test_force_bypasses_git_guard(sample_repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=sample_repo, check=True, capture_output=True)
    config = _config(sample_repo)
    config.safety.require_clean_git = True

    result = pipeline.update(sample_repo, config, State(), use_llm=False, force=True)
    assert result.written is True


def test_invalid_markers_generate_suggestion(sample_repo: Path) -> None:
    (sample_repo / "README.md").write_text(
        "# Sample\n\n<!-- epitaph:begin id=overview -->\nroto\n", encoding="utf-8"
    )
    config = _config(sample_repo)
    result = pipeline.update(sample_repo, config, State(), use_llm=False)

    assert result.written is False
    assert result.merge is not None and result.merge.errors
    assert (sample_repo / "README.suggested.md").exists()
    assert "roto" in (sample_repo / "README.md").read_text(encoding="utf-8")


def test_disabled_readme_writes_only_side_artifacts(sample_repo: Path) -> None:
    config = _config(sample_repo)
    config.features.readme = False
    before = (sample_repo / "README.md").read_text(encoding="utf-8")

    result = pipeline.update(sample_repo, config, State(), use_llm=False)

    assert result.written is False
    assert result.merge is None
    assert result.skipped_reason == "readme desactivado"
    assert (sample_repo / "README.md").read_text(encoding="utf-8") == before
    assert (sample_repo / "suggestions.md").exists()


def test_preferences_change_structure(sample_repo: Path) -> None:
    from epitaph.preferences import PreferenceStore

    config = _config(sample_repo)
    store = PreferenceStore.for_root(sample_repo)
    store.add("readme.structure", ["overview", "install", "license"])

    result = pipeline.update(sample_repo, config, State(), use_llm=False)
    assert result.written is True
    assert result.effective.sections == ["overview", "install", "license"]
    text = (sample_repo / "README.md").read_text(encoding="utf-8")
    assert "id=overview" in text
    assert "id=architecture" not in text
