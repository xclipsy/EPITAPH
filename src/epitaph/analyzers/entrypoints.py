"""Detección de puntos de entrada."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from .types import ModuleInfo


def _pyproject_scripts(root: Path) -> list[dict]:
    path = root / "pyproject.toml"
    if not path.exists():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return []
    entries: list[dict] = []
    project = data.get("project", {})
    for name, target in (project.get("scripts") or {}).items():
        entries.append({"path": "", "kind": "console_script", "command": f"{name} = {target}"})
    poetry = data.get("tool", {}).get("poetry", {})
    for name, target in (poetry.get("scripts") or {}).items():
        entries.append({"path": "", "kind": "console_script", "command": f"{name} = {target}"})
    return entries


def _package_json(root: Path) -> list[dict]:
    path = root / "package.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    entries: list[dict] = []
    for key in ("main", "module"):
        if isinstance(data.get(key), str):
            entries.append({"path": data[key], "kind": f"package_{key}", "command": ""})
    bin_field = data.get("bin")
    if isinstance(bin_field, str):
        entries.append({"path": bin_field, "kind": "package_bin", "command": ""})
    elif isinstance(bin_field, dict):
        for name, target in bin_field.items():
            entries.append({"path": target, "kind": "package_bin", "command": name})
    scripts = data.get("scripts") or {}
    for name in ("start", "dev", "serve"):
        if name in scripts:
            entries.append({"path": "", "kind": "npm_script", "command": f"npm run {name}"})
    return entries


def _docker(root: Path) -> list[dict]:
    for name in ("Dockerfile", "dockerfile"):
        path = root / name
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in re.finditer(r"^(?:CMD|ENTRYPOINT)\s+(.+)$", text, re.MULTILINE):
            return [{"path": name, "kind": "docker", "command": match.group(1).strip()}]
    return []


def detect_entrypoints(root: Path, modules: list[ModuleInfo]) -> list[dict]:
    entries: list[dict] = []
    for module in modules:
        if module.lang == "python":
            name = Path(module.path).name
            if name == "__main__.py":
                entries.append({"path": module.path, "kind": "module_main", "command": ""})
            elif module.has_main_guard:
                entries.append({"path": module.path, "kind": "main_guard", "command": ""})
    entries.extend(_pyproject_scripts(root))
    entries.extend(_package_json(root))
    entries.extend(_docker(root))

    unique: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        key = (entry.get("path", ""), entry.get("kind", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return unique
