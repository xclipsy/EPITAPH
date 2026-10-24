"""Escritura atómica de archivos."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .errors import ConfigError


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
    markers = (
        Path.cwd() / ".epitaph" / "active_workspace.txt",
        get_global_workspace_file(),
    )
    for marker in markers:
        if marker.exists():
            try:
                content = marker.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError) as exc:
                raise ConfigError(
                    f"No se pudo leer el workspace activo desde {marker}: {exc}",
                    hint="revisa los permisos del archivo o ejecuta `uv run epitaph init`",
                ) from exc
            if not content:
                raise ConfigError(
                    f"El workspace activo está vacío en {marker}",
                    hint="ejecuta `uv run epitaph init` para volver a configurarlo",
                )
            workspace = Path(content).expanduser().resolve()
            if not workspace.is_dir():
                raise ConfigError(
                    f"El workspace activo ya no existe: {workspace}",
                    hint="ejecuta `uv run epitaph init` o indica otra ruta con `-C`",
                )
            return workspace
    return None


def set_active_workspace(path: Path) -> None:
    """Guarda la ruta del workspace activo global y localmente."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise ConfigError(f"No se puede activar un workspace que no es un directorio: {resolved}")

    global_file = get_global_workspace_file()
    try:
        markers = [global_file]
        for directory in (Path.cwd() / ".epitaph", resolved / ".epitaph"):
            if directory.is_dir():
                marker = directory / "active_workspace.txt"
                if marker not in markers:
                    markers.append(marker)
        for marker in markers:
            atomic_write(marker, f"{resolved}\n")
    except OSError as exc:
        raise ConfigError(
            f"No se pudo guardar el workspace activo en {marker}: {exc}",
            hint="revisa los permisos de escritura y vuelve a ejecutar `uv run epitaph init`",
        ) from exc
