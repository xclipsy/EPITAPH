"""Detección determinista de intención: pregunta vs preferencia."""

from __future__ import annotations

import re
from dataclasses import dataclass

NEGATIVE = re.compile(
    r"\b(no quiero|no me gusta|no sugieras|no propongas|no recomiendes|evita|omite|"
    r"quita|elimina|silencia|oculta|sin)\b",
    re.IGNORECASE,
)
POSITIVE = re.compile(
    r"\b(prefiero|quiero que|me gustar[ií]a|usa|pon|coloca|ordena|mueve|escribe|"
    r"incluye|a[nñ]ade|agrega|mant[eé]n|sugiere)\b",
    re.IGNORECASE,
)

DOMAINS = {
    "readme.structure": re.compile(
        r"\b(secci[oó]n|secciones|estructura|[aá]rbol|orden|instalaci[oó]n|"
        r"arquitectura|arriba|abajo|final|principio)\b",
        re.IGNORECASE,
    ),
    "readme.style": re.compile(
        r"\b(tono|formal|informal|breve|detallado|verbosidad|extensi[oó]n|estilo|"
        r"ejemplos|badges)\b",
        re.IGNORECASE,
    ),
    "readme.language": re.compile(r"\b(idioma|ingl[eé]s|espa[nñ]ol|english|spanish)\b", re.IGNORECASE),
    "suggestions.modularity": re.compile(
        r"\b(modular|modularizaci[oó]n|capas|dominio|feature|features|carpeta|carpetas|"
        r"m[oó]dulo|m[oó]dulos|mover|reorganizar)\b",
        re.IGNORECASE,
    ),
    "suggestions.filter": re.compile(
        r"\b(sugerencia|sugerencias|sugieras|propongas|recomiendes|framework|"
        r"versi[oó]n|dependencia|dependencias|categor[ií]a)\b",
        re.IGNORECASE,
    ),
}


@dataclass
class Detection:
    is_preference: bool
    scope_hint: str | None = None
    confidence: float = 0.0
    matched: str = ""


def detect(text: str) -> Detection:
    raw = (text or "").strip()
    if not raw or raw.startswith("/"):
        return Detection(False)

    negative = bool(NEGATIVE.search(raw))
    positive = bool(POSITIVE.search(raw))
    if not (negative or positive):
        return Detection(False)

    scope: str | None = None
    for candidate, pattern in DOMAINS.items():
        if pattern.search(raw):
            scope = candidate
            break

    if scope is None:
        if positive:
            return Detection(True, "prompt.directives", 0.55, "verbo de preferencia")
        return Detection(False)

    confidence = 0.9 if (negative or positive) and scope else 0.7
    return Detection(True, scope, confidence, scope)
