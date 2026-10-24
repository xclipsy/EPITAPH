"""Descripción de un proyecto cualquiera: análisis determinista + prosa opcional."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .analyzers import analyze
from .config import Config
from .llm.contract import ProsePayload
from .llm.provider_ollama import OllamaProvider
from .pipeline import generate_prose
from .preferences import PreferenceStore, resolve
from .preferences.apply import apply_to_config
from .readme.merge import merge
from .readme.render import build_sections
from .ui.theme import PRIMARY, SECONDARY, SUCCESS, console, styled, write


@dataclass
class Description:
    root: Path
    facts: dict
    markdown: str = ""
    prose: ProsePayload | None = None
    used_llm: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "name": self.facts.get("name"),
            "languages": self.facts.get("languages", []),
            "totals": self.facts.get("totals", {}),
            "entrypoints": self.facts.get("entrypoints", []),
            "commands": self.facts.get("commands", {}),
            "cycles": self.facts.get("cycles", []),
            "orphans": self.facts.get("orphans", []),
            "dependencies": self.facts.get("dependencies", {}),
            "modules": [
                {
                    "path": module.get("path"),
                    "lang": module.get("lang"),
                    "loc": module.get("loc"),
                }
                for module in self.facts.get("modules", [])
            ],
            "prose": self.prose.model_dump() if self.prose else None,
            "markdown": self.markdown,
            "used_llm": self.used_llm,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "warnings": self.warnings,
        }


def describe(
    root: Path,
    *,
    config: Config | None = None,
    provider: OllamaProvider | None = None,
    use_llm: bool = False,
    on_token: Callable[[str], None] | None = None,
) -> Description:
    """Lee la carpeta indicada y devuelve su descripción (nunca escribe nada)."""
    root = Path(root).resolve()
    facts = analyze(root)
    settings = config or Config.load_or_default(root)
    settings.project.name = settings.project.name or root.name

    warnings: list[str] = []
    if facts.get("scanner_truncated"):
        warnings.append("se alcanzó el límite de archivos: la descripción está truncada")
    if not facts.get("modules"):
        warnings.append("no se encontró código fuente reconocible en la carpeta")

    store = PreferenceStore.for_root(
        root,
        settings.preferences.path,
        max_items=settings.preferences.max_directives,
    )
    effective = resolve(settings, store.items)
    effective_settings = apply_to_config(settings, effective)

    prose: ProsePayload | None = None
    tokens_in = tokens_out = 0
    if use_llm and provider is not None and facts.get("modules"):
        prose, tokens_in, tokens_out = generate_prose(
            root, facts, effective_settings, effective, provider, on_token=on_token
        )
        if prose is None:
            warnings.append("el modelo no devolvió prosa válida: se usa solo el análisis")

    sections = build_sections(facts, prose, effective_settings, root)
    markdown = merge(None, sections, title=facts.get("name", root.name)).text
    return Description(
        root=root,
        facts=facts,
        markdown=markdown,
        prose=prose,
        used_llm=prose is not None,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        warnings=warnings,
    )


def render(description: Description) -> None:
    """Imprime la descripción en la terminal."""
    facts = description.facts
    totals = facts.get("totals", {})

    if styled():
        console().print(
            f"\n[bold {PRIMARY}]{facts.get('name', description.root.name)}[/]  "
            f"[{SECONDARY}]{description.root}[/]"
        )
    else:
        print(f"\n{facts.get('name', description.root.name)}  {description.root}")

    _line("lenguajes", _languages(facts))
    _line(
        "tamaño",
        f"{totals.get('files', 0)} archivos · {totals.get('loc', 0)} líneas · "
        f"{totals.get('functions', 0)} funciones · {totals.get('classes', 0)} clases",
    )
    _line(
        "salud",
        f"mantenibilidad media {totals.get('avg_maintainability', 0)} · "
        f"complejidad media {totals.get('avg_cyclomatic', 0)}",
    )
    entrypoints = facts.get("entrypoints", [])
    if entrypoints:
        _line("entradas", ", ".join(entry.get("path", "?") for entry in entrypoints[:6]))
    commands = facts.get("commands", {})
    if commands.get("run"):
        _line("ejecutar", " · ".join(commands["run"][:4]))
    if commands.get("test"):
        _line("tests", " · ".join(commands["test"][:3]))

    modules = sorted(facts.get("modules", []), key=lambda item: item.get("loc", 0), reverse=True)
    if modules:
        _line("módulos", "")
        notes = {note.path: note.purpose for note in (description.prose.module_notes if description.prose else [])}
        for module in modules[:8]:
            purpose = notes.get(module.get("path", ""), "")
            suffix = f" — {purpose}" if purpose else ""
            _bullets(f"{module.get('path')} ({module.get('loc', 0)} líneas){suffix}")

    cycles = facts.get("cycles", [])
    orphans = facts.get("orphans", [])
    if cycles or orphans:
        _line("riesgos", f"{len(cycles)} ciclos · {len(orphans)} módulos huérfanos")

    if description.prose and description.prose.overview:
        _section("Resumen", description.prose.overview)
    if description.prose and description.prose.architecture_note:
        _section("Arquitectura", description.prose.architecture_note)
    if description.prose and description.prose.asks:
        _section("Falta información", " ".join(description.prose.asks[:4]))

    for warning in description.warnings:
        _line("aviso", warning)

    if description.used_llm:
        _line("modelo", f"{description.tokens_out} tokens de salida")
    else:
        _line("modelo", "no usado (solo análisis determinista)")


def _languages(facts: dict) -> str:
    languages = facts.get("languages", [])
    if not languages:
        return "sin lenguajes de código reconocidos"
    parts = [
        f"{item.get('name')} ({item.get('files', 0)} archivos, {item.get('loc', 0)} líneas)"
        for item in languages[:4]
    ]
    return " · ".join(parts)


def _line(label: str, value: str) -> None:
    if styled():
        console().print(f"[{SECONDARY}]{label:<12}[/] {value}")
    else:
        print(f"{label:<12} {value}")


def _bullets(text: str) -> None:
    if styled():
        console().print(f"[{SECONDARY}]  · [/]{text}")
    else:
        print(f"  · {text}")


def _section(title: str, body: str) -> None:
    if styled():
        console().print(f"\n[bold {SUCCESS}]{title}[/]")
    else:
        print(f"\n{title}")
    write(body.strip() + "\n")
