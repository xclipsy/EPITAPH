"""Aplicación de preferencias a configuración, prompts y sugerencias."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from ..config import Config
from .store import Preference

DEFAULT_SECTIONS = [
    "overview",
    "install",
    "usage",
    "structure",
    "architecture",
    "requirements",
    "development",
    "license",
]


@dataclass
class Effective:
    sections: list[str] = field(default_factory=lambda: list(DEFAULT_SECTIONS))
    include_badges: bool = False
    tone: str = "neutral"
    verbosity: str = "normal"
    language: str = "es"
    modularity: str = "by-layer"
    forbidden: list[str] = field(default_factory=list)
    muted: list[str] = field(default_factory=list)
    severity: str = "low"
    naming: dict[str, str] = field(default_factory=dict)
    directives: list[str] = field(default_factory=list)


def resolve(config: Config, preferences: list[Preference]) -> Effective:
    effective = Effective(
        sections=list(config.readme.sections),
        include_badges=config.readme.include_badges,
        tone=config.readme.tone,
        verbosity=config.readme.verbosity,
        language=config.project.output_language,
    )

    # config explícita gana: solo se aplica estructura si sigue siendo la default
    explicit_sections = config.readme.sections != DEFAULT_SECTIONS
    explicit_language = config.project.output_language != "es"

    for preference in preferences:
        scope = preference.scope
        value = preference.value
        if scope == "readme.structure" and isinstance(value, list) and not explicit_sections:
            effective.sections = [item for item in value if isinstance(item, str)]
        elif scope == "readme.style" and isinstance(value, dict):
            if "include_badges" in value:
                effective.include_badges = bool(value["include_badges"])
            if value.get("tone"):
                effective.tone = str(value["tone"])
            if value.get("verbosity"):
                effective.verbosity = str(value["verbosity"])
        elif scope == "readme.language" and isinstance(value, str) and not explicit_language:
            effective.language = value
        elif scope == "suggestions.modularity" and isinstance(value, str):
            effective.modularity = value
        elif scope == "suggestions.filter" and isinstance(value, dict):
            if isinstance(value.get("forbidden"), list):
                effective.forbidden = [str(item) for item in value["forbidden"]]
            if isinstance(value.get("muted"), list):
                effective.muted = [str(item) for item in value["muted"]]
            if value.get("severity"):
                effective.severity = str(value["severity"])
        elif scope == "suggestions.naming" and isinstance(value, dict):
            effective.naming = {str(key): str(item) for key, item in value.items()}
        elif scope == "prompt.directives" and isinstance(value, str):
            effective.directives.append(value)

    return effective


def apply_to_config(config: Config, effective: Effective) -> Config:
    updated = copy.deepcopy(config)
    updated.readme.sections = list(effective.sections)
    updated.readme.include_badges = effective.include_badges
    updated.readme.tone = effective.tone
    updated.readme.verbosity = effective.verbosity
    updated.project.output_language = effective.language
    return updated


def directives_text(effective: Effective, max_chars: int = 800) -> str:
    lines: list[str] = []
    if effective.directives:
        lines.extend(f"- {directive}" for directive in effective.directives)
    lines.append(f"- Tono: {effective.tone}; verbosidad: {effective.verbosity}.")
    if not effective.include_badges:
        lines.append("- No incluir badges.")
    if effective.modularity != "by-layer":
        lines.append(f"- Sugerencias de modularización orientadas a: {effective.modularity}.")
    if effective.naming:
        mapping = ", ".join(f"{key}→{value}" for key, value in effective.naming.items())
        lines.append(f"- Vocabulario del proyecto: {mapping}.")
    if effective.forbidden:
        lines.append("- No proponer: " + ", ".join(effective.forbidden) + ".")
    if effective.muted:
        lines.append("- Omitir categorías: " + ", ".join(effective.muted) + ".")
    text = "\n".join(lines)
    return text[:max_chars]


def filter_suggestions(items: list[dict], effective: Effective) -> tuple[list[dict], int]:
    severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    minimum = severity_order.get(effective.severity, 0)
    kept: list[dict] = []
    hidden = 0
    for item in items:
        if item.get("category") == "security":
            kept.append(item)
            continue
        if item.get("category") in effective.muted:
            hidden += 1
            continue
        if item.get("rule") in effective.forbidden:
            hidden += 1
            continue
        if severity_order.get(item.get("severity", "low"), 0) < minimum:
            hidden += 1
            continue
        kept.append(item)
    return kept, hidden
