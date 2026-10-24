"""Detección de módulos huérfanos (código muerto probable)."""

from __future__ import annotations

from pathlib import PurePosixPath

from .types import ModuleInfo

EXEMPT_NAMES = {
    "__init__.py",
    "__main__.py",
    "conftest.py",
    "setup.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "noxfile.py",
    "fabfile.py",
}

EXEMPT_PARTS = {"tests", "test", "migrations", "scripts", "examples", "docs"}


def find_orphans(
    modules: list[ModuleInfo],
    graph: dict[str, set[str]],
    entrypoints: list[dict],
) -> list[str]:
    imported: set[str] = set()
    for targets in graph.values():
        imported.update(targets)

    entry_paths = {entry.get("path", "") for entry in entrypoints if entry.get("path")}

    orphans: list[str] = []
    for module in modules:
        if module.lang != "python":
            continue
        name = PurePosixPath(module.path).name
        parts = set(PurePosixPath(module.path).parts[:-1])
        if name in EXEMPT_NAMES:
            continue
        if parts & EXEMPT_PARTS:
            continue
        if module.path in entry_paths or module.has_main_guard:
            continue
        if module.path in imported:
            continue
        orphans.append(module.path)

    return sorted(orphans)
