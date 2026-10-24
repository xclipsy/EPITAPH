"""Copias de seguridad con retención."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def backup_file(path: Path, root: Path, retention: int = 20) -> Path | None:
    path = Path(path)
    if not path.exists():
        return None
    directory = Path(root) / ".epitaph" / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    target = directory / f"{path.name}.{stamp}.bak"
    shutil.copy2(path, target)
    _prune(directory, path.name, retention)
    return target


def _prune(directory: Path, name: str, retention: int) -> None:
    if retention <= 0:
        return
    candidates = sorted(directory.glob(f"{name}.*.bak"), key=lambda item: item.stat().st_mtime)
    for old in candidates[:-retention]:
        try:
            old.unlink()
        except OSError:
            pass


def list_backups(root: Path, name: str | None = None) -> list[Path]:
    directory = Path(root) / ".epitaph" / "backups"
    if not directory.exists():
        return []
    pattern = f"{name}.*.bak" if name else "*.bak"
    return sorted(directory.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)


def restore(backup: Path, destination: Path) -> None:
    shutil.copy2(backup, destination)
