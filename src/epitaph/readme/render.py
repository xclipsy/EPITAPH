"""Renderizado determinista de las secciones del README."""

from __future__ import annotations

import tomllib
from collections import OrderedDict
from pathlib import Path

from ..config import Config
from ..llm.contract import ProsePayload

SECTION_TITLES = {
    "overview": "Descripción",
    "install": "Instalación",
    "usage": "Uso",
    "structure": "Estructura del proyecto",
    "architecture": "Arquitectura",
    "requirements": "Requisitos",
    "development": "Desarrollo",
    "license": "Licencia",
}


def build_sections(
    facts: dict,
    prose: ProsePayload | None,
    config: Config,
    root: Path,
) -> OrderedDict[str, str]:
    builders = {
        "overview": lambda: _overview(facts, prose),
        "install": lambda: _install(facts),
        "usage": lambda: _usage(facts),
        "structure": lambda: _structure(facts, prose, config),
        "architecture": lambda: _architecture(facts, prose),
        "requirements": lambda: _requirements(facts, root),
        "development": lambda: _development(facts),
        "license": lambda: _license(root),
    }

    sections: OrderedDict[str, str] = OrderedDict()
    for section_id in config.readme.sections[: config.readme.max_sections]:
        builder = builders.get(section_id)
        if builder is None:
            continue
        content = builder()
        if content and content.strip():
            sections[section_id] = content
    return sections


def _heading(section_id: str) -> str:
    return f"## {SECTION_TITLES.get(section_id, section_id.title())}"


def _overview(facts: dict, prose: ProsePayload | None) -> str:
    if prose and prose.overview.strip():
        body = prose.overview.strip()
    else:
        languages = ", ".join(item["name"] for item in facts.get("languages", [])[:3])
        totals = facts.get("totals", {})
        body = (
            f"`{facts.get('name', 'proyecto')}` es un proyecto"
            f"{f' escrito en {languages}' if languages else ''} con "
            f"{totals.get('files', 0)} archivos de código y "
            f"{totals.get('loc', 0)} líneas."
        )
    return f"{_heading('overview')}\n\n{body}"


def _install(facts: dict) -> str | None:
    commands = facts.get("commands", {}).get("install", [])
    if not commands:
        return None
    lines = [f"```bash\n{command}\n```" for command in commands]
    return f"{_heading('install')}\n\n" + "\n\n".join(lines)


def _usage(facts: dict) -> str | None:
    commands = facts.get("commands", {}).get("run", [])
    entrypoints = [entry for entry in facts.get("entrypoints", []) if entry.get("path")]
    if not commands and not entrypoints:
        return None
    parts = [f"{_heading('usage')}"]
    if commands:
        parts.append("\n".join(f"```bash\n{command}\n```" for command in commands))
    if entrypoints:
        listing = "\n".join(
            f"- `{entry['path']}` ({entry.get('kind', 'entrada')})" for entry in entrypoints[:8]
        )
        parts.append(f"Puntos de entrada detectados:\n\n{listing}")
    return "\n\n".join(parts)


def _structure(facts: dict, prose: ProsePayload | None, config: Config) -> str | None:
    parts = [_heading("structure")]
    if config.readme.include_tree:
        tree = render_tree(facts.get("tree", {}), config.readme.tree_depth)
        if tree:
            parts.append(f"```text\n{tree}\n```")
    if prose and prose.module_notes:
        notes = "\n".join(
            f"- `{note.path}` — {note.purpose}" for note in prose.module_notes[:20]
        )
        parts.append(notes)
    if len(parts) == 1:
        return None
    return "\n\n".join(parts)


def _architecture(facts: dict, prose: ProsePayload | None) -> str | None:
    parts = [_heading("architecture")]
    if prose and prose.architecture_note.strip():
        parts.append(prose.architecture_note.strip())

    cycles = facts.get("cycles", [])
    orphans = facts.get("orphans", [])
    details: list[str] = []
    if cycles:
        rendered = "; ".join(" → ".join(cycle) for cycle in cycles[:3])
        details.append(f"- Dependencias circulares detectadas: {rendered}")
    if orphans:
        details.append(
            "- Posibles módulos sin uso: " + ", ".join(f"`{item}`" for item in orphans[:8])
        )
    if details:
        parts.append("\n".join(details))
    if len(parts) == 1:
        return None
    return "\n\n".join(parts)


def _requirements(facts: dict, root: Path) -> str | None:
    parts = [_heading("requirements")]
    parts.append(f"- Python {_python_requirement(root)}")
    declared = _declared_dependencies(root)
    if declared:
        parts.append("Dependencias declaradas:\n\n" + "\n".join(f"- `{dep}`" for dep in declared[:15]))
    elif facts.get("dependencies", {}).get("python_imports"):
        imports = facts["dependencies"]["python_imports"][:15]
        parts.append(
            "Dependencias detectadas en el código (sin archivo de requisitos):\n\n"
            + "\n".join(f"- `{dep}`" for dep in imports)
        )
    return "\n\n".join(parts)


def _development(facts: dict) -> str | None:
    commands = facts.get("commands", {})
    lines: list[str] = []
    for key, label in (("test", "Pruebas"), ("lint", "Lint")):
        values = commands.get(key, [])
        if values:
            lines.append(f"{label}:\n\n" + "\n".join(f"```bash\n{value}\n```" for value in values))
    if not lines:
        return None
    return f"{_heading('development')}\n\n" + "\n\n".join(lines)


def _license(root: Path) -> str | None:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
        path = root / name
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:600].lower()
        except OSError:
            continue
        if "mit license" in text:
            return f"{_heading('license')}\n\nMIT — ver [`{name}`]({name})."
        if "apache license" in text:
            return f"{_heading('license')}\n\nApache 2.0 — ver [`{name}`]({name})."
        if "gnu general public license" in text:
            return f"{_heading('license')}\n\nGPL — ver [`{name}`]({name})."
        if "bsd" in text:
            return f"{_heading('license')}\n\nBSD — ver [`{name}`]({name})."
        return f"{_heading('license')}\n\nVer [`{name}`]({name})."
    return None


def _declared_dependencies(root: Path) -> list[str]:
    entries: list[str] = []

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError):
            data = {}
        project = data.get("project", {})
        for dependency in project.get("dependencies", []) or []:
            if isinstance(dependency, str):
                entries.append(dependency)
        poetry = data.get("tool", {}).get("poetry", {})
        for name in (poetry.get("dependencies") or {}):
            if name.lower() != "python":
                entries.append(name)

    path = root / "requirements.txt"
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        entries.extend(
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith(("#", "-"))
        )

    return list(dict.fromkeys(entries))


def _python_requirement(root: Path) -> str:
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError):
            data = {}
        value = data.get("project", {}).get("requires-python")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "3.12+"


def render_tree(tree: dict, max_depth: int = 3) -> str:
    lines: list[str] = []

    def walk(node: dict, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        children = node.get("children", {})
        if not isinstance(children, dict):
            return
        ordered = sorted(
            children.values(),
            key=lambda item: (item.get("type") != "dir", item.get("name", "").lower()),
        )
        for index, child in enumerate(ordered):
            last = index == len(ordered) - 1
            connector = "└── " if last else "├── "
            suffix = "/" if child.get("type") == "dir" else ""
            lines.append(f"{prefix}{connector}{child.get('name', '')}{suffix}")
            if child.get("type") == "dir" and depth < max_depth:
                extension = "    " if last else "│   "
                walk(child, prefix + extension, depth + 1)

    lines.append(f"{tree.get('name', 'proyecto')}/")
    walk(tree, "", 1)
    if len(lines) == 1:
        return ""
    return "\n".join(lines[:120])
