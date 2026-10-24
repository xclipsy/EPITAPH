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


# Artefactos propios que no deben contar como "árbol sucio": el wizard crea
# .epitaph/ antes del primer update y la salida generada se regenera sola.
IGNORED_PREFIXES = (".epitaph/",)
IGNORED_FILES = {
    "suggestions.md",
    "requirements.suggested.txt",
    "README.suggested.md",
}


def _is_own_artifact(raw_path: str) -> bool:
    path = raw_path.strip().strip('"')
    if " -> " in path:  # renombrados en porcelain v1: "R  viejo -> nuevo"
        path = path.split(" -> ")[-1].strip().strip('"')
    return path.startswith(IGNORED_PREFIXES) or path in IGNORED_FILES


def status(root: Path) -> tuple[bool, str]:
    """Devuelve (árbol_limpio, salida_de_status).

    Se ignoran los artefactos que gestiona EPITAPH (`.epitaph/`,
    `suggestions.md`, `requirements.suggested.txt`, `README.suggested.md`).
    Así `init` no bloquea el primer `update` y la salida generada no impide
    escribir el README.
    """
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

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    dirty = [line for line in lines if not _is_own_artifact(line[3:])]
    return not dirty, "\n".join(dirty)


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
