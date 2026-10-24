"""Escritura atómica de archivos."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, content: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def get_global_workspace_file() -> Path:
    return Path.home() / ".config" / "epitaph" / "active_workspace.txt"


def get_active_workspace() -> Path | None:
    """Retorna la ruta del workspace activo persistido, si existe."""
    # 1. Archivo local de active_workspace en .epitaph/ del directorio actual
    local_file = Path.cwd() / ".epitaph" / "active_workspace.txt"
    if local_file.exists():
        try:
            content = local_file.read_text(encoding="utf-8").strip()
            if content:
                p = Path(content).expanduser().resolve()
                if p.exists() and p.is_dir():
                    return p
        except Exception:
            pass

    # 2. Archivo global ~/.config/epitaph/active_workspace.txt
    global_file = get_global_workspace_file()
    if global_file.exists():
        try:
            content = global_file.read_text(encoding="utf-8").strip()
            if content:
                p = Path(content).expanduser().resolve()
                if p.exists() and p.is_dir():
                    return p
        except Exception:
            pass
    return None


def set_active_workspace(path: Path) -> None:
    """Guarda la ruta del workspace activo global y localmente."""
    resolved = Path(path).expanduser().resolve()

    # 1. Global
    global_file = get_global_workspace_file()
    try:
        global_file.parent.mkdir(parents=True, exist_ok=True)
        global_file.write_text(str(resolved), encoding="utf-8")
    except Exception:
        pass

    # 2. Local en cwd/.epitaph
    cwd_epitaph = Path.cwd() / ".epitaph"
    if cwd_epitaph.exists() and cwd_epitaph.is_dir():
        try:
            (cwd_epitaph / "active_workspace.txt").write_text(str(resolved), encoding="utf-8")
        except Exception:
            pass

    # 3. Local en workspace/.epitaph
    target_epitaph = resolved / ".epitaph"
    if target_epitaph.exists() and target_epitaph.is_dir():
        try:
            (target_epitaph / "active_workspace.txt").write_text(str(resolved), encoding="utf-8")
        except Exception:
            pass
