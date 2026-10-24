"""Análisis de imports frente a dependencias declaradas."""

from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath

from ..config import Config
from .alias_map import AMBIGUOUS, normalize, package_for

STDLIB = set(sys.stdlib_module_names) | {"__future__", "typing_extensions"}


def _internal_roots(facts: dict) -> set[str]:
    """Raíces importables que pertenecen al propio repositorio.

    `from src.app.core import run` no es una dependencia externa: `src` y `app`
    son paquetes del proyecto. Se derivan de las rutas analizadas.
    """
    roots: set[str] = set()
    for module in facts.get("modules", []):
        parts = PurePosixPath(module.get("path", "")).with_suffix("").parts
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        for start in range(len(parts)):
            roots.add(parts[start])
    return roots


def collect_imports(facts: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    internal = _internal_roots(facts)
    for module in facts.get("modules", []):
        for ref in module.get("imports", []):
            if ref.get("level") != 0:
                continue
            name = (ref.get("module") or "").split(".")[0]
            if not name or name in STDLIB or name.startswith("_"):
                continue
            if name in internal:
                continue
            counts[name] = counts.get(name, 0) + 1
    return counts


def declared(root: Path, config: Config) -> list[str]:
    path = Path(root) / config.requirements.path
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith(("#", "-r", "-e"))
    ]


def analyze(root: Path, facts: dict, config: Config) -> dict:
    imports = collect_imports(facts)
    declared_lines = declared(root, config)
    declared_names = {normalize(line) for line in declared_lines}

    missing: list[dict] = []
    for import_name, count in sorted(imports.items(), key=lambda item: (-item[1], item[0])):
        package = package_for(import_name)
        if normalize(package) in declared_names or normalize(import_name) in declared_names:
            continue
        missing.append(
            {
                "import": import_name,
                "package": package,
                "count": count,
                "ambiguous": AMBIGUOUS.get(import_name),
            }
        )

    imported_normalized = {normalize(package_for(name)) for name in imports} | {
        normalize(name) for name in imports
    }
    unused = [
        line
        for line in declared_lines
        if normalize(line) not in imported_normalized
    ]

    return {
        "declared": declared_lines,
        "imports": imports,
        "missing": missing,
        "unused": unused,
    }


def suggest_versions(missing: list[dict]) -> list[str]:
    lines: list[str] = []
    for item in missing:
        if item.get("ambiguous"):
            lines.append(f"# {item['package']}: {item['ambiguous']}")
            continue
        lines.append(item["package"])
    return lines
