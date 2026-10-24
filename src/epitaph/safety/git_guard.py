"""Verificación del árbol de git antes de escribir."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def git_available() -> bool:
    return shutil.which("git") is not None


def is_repo(root: Path) -> bool:
    if not git_available():
        return False
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except (subprocess.SubprocessError, OSError):
        return False


def status(root: Path) -> tuple[bool, str]:
    """Devuelve (árbol_limpio, salida_de_status)."""
    if not is_repo(root):
        return True, "no es un repositorio git"
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return True, "no se pudo ejecutar git status"
    output = result.stdout.strip()
    return output == "", output


def diff(root: Path, path: str) -> str:
    if not is_repo(root):
        return ""
    try:
        result = subprocess.run(
            ["git", "diff", "--", path],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout
    except (subprocess.SubprocessError, OSError):
        return ""
