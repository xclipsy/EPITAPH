"""Construcción y validación de propuestas de preferencia."""

from __future__ import annotations

import re

from ..config import Config
from ..llm.contract import ALLOWED_SCOPES, PreferenceProposal

KNOWN_SECTIONS = {
    "overview": ("descripci", "overview", "introducci"),
    "install": ("instalaci", "install"),
    "usage": ("uso", "usage", "ejecuci", "comando"),
    "structure": ("estructura", "árbol", "arbol", "tree", "carpetas"),
    "architecture": ("arquitectura", "architecture"),
    "requirements": ("requisito", "requerimiento", "requeriments", "dependencia"),
    "development": ("desarrollo", "development", "prueba", "test", "lint"),
    "license": ("licencia", "license"),
}

MODULARITY = {
    "dominio": "by-domain",
    "domain": "by-domain",
    "feature": "by-feature",
    "funcionalidad": "by-feature",
    "capa": "by-layer",
    "layer": "by-layer",
    "plano": "flat",
    "flat": "flat",
}


def _section_for(word: str) -> str | None:
    lowered = word.lower()
    for section, needles in KNOWN_SECTIONS.items():
        if any(needle in lowered for needle in needles):
            return section
    return None


def _move(sections: list[str], target: str, position: str) -> list[str]:
    if target not in sections:
        return sections
    result = [section for section in sections if section != target]
    if position == "first":
        result.insert(0, target)
    elif position == "last":
        result.append(target)
    return result


def build(
    text: str,
    scope_hint: str | None,
    config: Config,
    existing_count: int = 0,
) -> PreferenceProposal | None:
    raw = (text or "").strip()
    lowered = raw.lower()
    if not raw:
        return None

    negative = bool(re.search(r"\b(no|sin|quita|elimina|evita|omite)\b", lowered))
    position_last = bool(re.search(r"\b(final|al final|abajo|[uú]ltimo|despu[eé]s)\b", lowered))
    position_first = bool(re.search(r"\b(primero|al principio|arriba|inicio)\b", lowered))

    # ---------------------------------------------------------- estructura
    if scope_hint == "readme.structure" or "readme" in lowered or "secci" in lowered:
        sections = list(config.readme.sections)

        if "badge" in lowered:
            return _proposal("readme.style", {"include_badges": not negative}, raw)

        if ("árbol" in lowered or "arbol" in lowered or "tree" in lowered or "estructura" in lowered) and (
            position_last or position_first
        ):
            moved = _move(sections, "structure", "last" if position_last else "first")
            if moved != sections:
                return _proposal("readme.structure", moved, raw)

        if "instalaci" in lowered and (position_first or position_last):
            moved = _move(sections, "install", "first" if position_first else "last")
            if moved != sections:
                return _proposal("readme.structure", moved, raw)

        match = re.search(r"(?:quita|elimina|omite|sin)\s+(?:la\s+)?secci[oó]n\s+([\wáéíóúñ]+)", lowered)
        if match:
            target = _section_for(match.group(1))
            if target and target in sections:
                return _proposal(
                    "readme.structure", [item for item in sections if item != target], raw
                )

        if position_last or position_first:
            target = next(
                (section for section in KNOWN_SECTIONS if section in lowered),
                None,
            )
            if target is None:
                for word in re.findall(r"[a-záéíóúñ]+", lowered):
                    target = _section_for(word)
                    if target:
                        break
            if target:
                moved = _move(sections, target, "last" if position_last else "first")
                if moved != sections:
                    return _proposal("readme.structure", moved, raw)

    # -------------------------------------------------------------- estilo
    if scope_hint == "readme.style":
        style: dict = {}
        if "informal" in lowered:
            style["tone"] = "informal"
        elif "formal" in lowered:
            style["tone"] = "formal"
        if "breve" in lowered or "corto" in lowered:
            style["verbosity"] = "breve"
        elif "detallado" in lowered or "extenso" in lowered:
            style["verbosity"] = "detallado"
        if "badge" in lowered:
            style["include_badges"] = not negative
        if style:
            return _proposal("readme.style", style, raw)

    # ------------------------------------------------------------- idioma
    if scope_hint == "readme.language":
        if "ingl" in lowered or "english" in lowered:
            return _proposal("readme.language", "en", raw)
        if "espa" in lowered or "spanish" in lowered:
            return _proposal("readme.language", "es", raw)

    # -------------------------------------------------------- modularidad
    if scope_hint == "suggestions.modularity":
        for needle, style in MODULARITY.items():
            if needle in lowered:
                return _proposal("suggestions.modularity", style, raw)

    # ----------------------------------------------------------- filtros
    if scope_hint == "suggestions.filter":
        forbidden: list[str] = []
        muted: list[str] = []
        if negative and ("framework" in lowered):
            forbidden.append("framework-change")
        if negative and "versi" in lowered:
            forbidden.append("dependency-upgrade")
        for category in ("tooling", "documentation", "dead-code", "architecture", "dependencies"):
            if negative and category.replace("-", " ") in lowered:
                muted.append(category)
        if forbidden or muted:
            value: dict = {}
            if forbidden:
                value["forbidden"] = forbidden
            if muted:
                value["muted"] = muted
            return _proposal("suggestions.filter", value, raw)

    # ---------------------------------------------------------- directiva
    if scope_hint == "prompt.directives" or existing_count < config.preferences.max_directives:
        if len(raw) <= config.preferences.max_directive_chars:
            return _proposal("prompt.directives", raw, raw, confidence=0.55)

    return None


def _proposal(scope: str, value, note: str, confidence: float = 0.85) -> PreferenceProposal:
    return PreferenceProposal(
        scope=scope,
        value=value,
        reason=note[:240],
        confidence=confidence,
        requires_confirmation=True,
    )


def validate(proposal: PreferenceProposal, config: Config) -> tuple[bool, str]:
    if proposal.scope not in ALLOWED_SCOPES:
        return False, f"ámbito no permitido: {proposal.scope}"

    value = proposal.value
    if proposal.scope == "readme.structure":
        if not isinstance(value, list) or not value:
            return False, "la estructura debe ser una lista no vacía de secciones"
        if any(not isinstance(item, str) or item not in KNOWN_SECTIONS for item in value):
            return False, "hay secciones desconocidas en la estructura"
        if len(set(value)) != len(value):
            return False, "hay secciones duplicadas"
        return True, ""

    if proposal.scope == "readme.style":
        if not isinstance(value, dict) or not value:
            return False, "el estilo debe ser un objeto con al menos un campo"
        allowed = {"tone", "verbosity", "include_badges", "tree_depth"}
        if set(value) - allowed:
            return False, "campos de estilo no permitidos"
        if "tone" in value and value["tone"] not in ("neutral", "formal", "informal"):
            return False, "tono no permitido"
        if "verbosity" in value and value["verbosity"] not in ("breve", "normal", "detallado"):
            return False, "verbosidad no permitida"
        return True, ""

    if proposal.scope == "readme.language":
        if not isinstance(value, str) or not re.fullmatch(r"[a-z]{2}(-[A-Za-z]{2,4})?", value):
            return False, "idioma inválido"
        return True, ""

    if proposal.scope == "suggestions.modularity":
        if value not in ("by-layer", "by-feature", "by-domain", "flat"):
            return False, "estilo de modularización no permitido"
        return True, ""

    if proposal.scope == "suggestions.filter":
        if not isinstance(value, dict) or not value:
            return False, "el filtro debe ser un objeto"
        if set(value) - {"forbidden", "muted", "severity"}:
            return False, "campos de filtro no permitidos"
        if "severity" in value and value["severity"] not in ("low", "medium", "high", "critical"):
            return False, "severidad no permitida"
        for key in ("forbidden", "muted"):
            if key in value and (
                not isinstance(value[key], list) or not all(isinstance(item, str) for item in value[key])
            ):
                return False, f"'{key}' debe ser una lista de textos"
        return True, ""

    if proposal.scope == "suggestions.naming":
        if not isinstance(value, dict) or len(value) > 20:
            return False, "el mapa de nombres debe tener como máximo 20 entradas"
        if not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
            return False, "el mapa de nombres debe ser texto → texto"
        return True, ""

    if proposal.scope == "prompt.directives":
        if not isinstance(value, str) or not value.strip():
            return False, "la directiva está vacía"
        if len(value) > config.preferences.max_directive_chars:
            return False, "la directiva es demasiado larga"
        if re.search(r"```|https?://", value):
            return False, "las directivas no admiten bloques de código ni URLs"
        if re.search(r"\b(permiso|permission|escribe\s+requirements|sin\s+preguntar)\b", value.lower()):
            return False, "las preferencias no pueden cambiar permisos; usa /permissions"
        return True, ""

    return False, "ámbito no implementado"


def conflicts(proposal: PreferenceProposal, existing: list) -> list[str]:
    notes: list[str] = []
    for preference in existing:
        if preference.scope != proposal.scope:
            continue
        if proposal.scope == "suggestions.modularity" and preference.value != proposal.value:
            notes.append(f"contradice a {preference.id}: {preference.value} → {proposal.value}")
        if proposal.scope == "readme.language" and preference.value != proposal.value:
            notes.append(f"contradice a {preference.id}: {preference.value} → {proposal.value}")
    return notes
