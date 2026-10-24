"""Generación de requirements.suggested.txt y su diff."""

from __future__ import annotations

import difflib
from pathlib import Path

from ..config import Config


def build_suggested(result: dict) -> str:
    declared = result.get("declared", [])
    missing = result.get("missing", [])
    unused = result.get("unused", [])

    if not missing and not unused:
        return (
            "# Generado por EPITAPH\n"
            "# Sin cambios: las dependencias declaradas coinciden con los imports.\n"
        )

    lines = ["# Generado por EPITAPH", "# Revisa y aplica manualmente.", ""]

    if declared:
        lines.extend(declared)
        lines.append("")

    if missing:
        lines.append("# Faltantes detectados en el código:")
        for item in missing:
            if item.get("ambiguous"):
                lines.append(f"# revisar: {item['package']} ({item['ambiguous']})")
            else:
                lines.append(item["package"])
        lines.append("")

    if unused:
        lines.append("# Declarados sin uso detectado (revisar antes de eliminar):")
        lines.extend(f"# {line}" for line in unused)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def unified_diff(original: str, suggested: str, path: str = "requirements.txt") -> str:
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            suggested.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def write_suggested(root: Path, config: Config, result: dict) -> Path:
    suggested = build_suggested(result)
    target = Path(root) / "requirements.suggested.txt"
    target.write_text(suggested, encoding="utf-8")
    return target


def render_diff(root: Path, config: Config, result: dict) -> str:
    original_path = Path(root) / config.requirements.path
    original = original_path.read_text(encoding="utf-8") if original_path.exists() else ""
    return unified_diff(original, build_suggested(result), config.requirements.path)
