from __future__ import annotations

from pathlib import Path

from epitaph import safety
from epitaph.config import Config


def test_permission_matrix_defaults() -> None:
    config = Config.default("demo")
    assert safety.check(config, "read") == "allow"
    assert safety.check(config, "write:readme") == "ask"
    assert safety.check(config, "write:requirements") == "deny"
    assert safety.check(config, "write:suggestions") == "allow"
    assert safety.check(config, "write:code") == "deny"
    assert safety.check(config, "network") == "deny"
    assert safety.check(config, "unknown:action") == "deny"


def test_network_flag_is_boolean() -> None:
    config = Config.default("demo")
    config.permissions.network = True
    assert safety.check(config, "network") == "allow"


def test_backup_and_restore(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("original\n", encoding="utf-8")

    backup = safety.backup_file(readme, tmp_path, retention=5)
    assert backup is not None
    assert backup.exists()

    readme.write_text("modificado\n", encoding="utf-8")
    backups = safety.list_backups(tmp_path, "README.md")
    assert backups and backups[0] == backup

    safety.restore(backup, readme)
    assert readme.read_text(encoding="utf-8") == "original\n"


def test_backup_of_missing_file_is_noop(tmp_path: Path) -> None:
    assert safety.backup_file(tmp_path / "nope.md", tmp_path) is None


def test_backup_retention_prunes_old_files(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("v0\n", encoding="utf-8")
    for _ in range(4):
        safety.backup_file(readme, tmp_path, retention=2)

    backups = safety.list_backups(tmp_path, "README.md")
    assert len(backups) == 2


def test_audit_log_is_append_only(tmp_path: Path) -> None:
    safety.log(tmp_path, "write:readme", file="README.md", tokens_in=10)
    safety.log(tmp_path, "undo:readme", backup="x.bak")

    events = safety.tail(tmp_path, limit=10)
    assert [event["action"] for event in events] == ["write:readme", "undo:readme"]
    assert events[0]["file"] == "README.md"
    assert "ts" in events[0]


def test_audit_tail_of_missing_log(tmp_path: Path) -> None:
    assert safety.tail(tmp_path) == []


def test_git_status_on_plain_directory(tmp_path: Path) -> None:
    clean, reason = safety.status(tmp_path)
    assert clean is True
    assert "git" in reason
