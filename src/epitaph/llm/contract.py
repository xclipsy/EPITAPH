"""Contrato de salida del modelo: JSON validado, nunca escrituras directas."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ..errors import InvalidModelOutput

PROMPT_VERSION = 1

ALLOWED_SCOPES = {
    "readme.structure",
    "readme.style",
    "readme.language",
    "suggestions.modularity",
    "suggestions.filter",
    "suggestions.naming",
    "prompt.directives",
}


class ModuleNote(BaseModel):
    path: str
    purpose: str = Field(default="", max_length=180)


class ProsePayload(BaseModel):
    overview: str = ""
    architecture_note: str = ""
    module_notes: list[ModuleNote] = Field(default_factory=list)
    confidence: float = 0.0
    asks: list[str] = Field(default_factory=list)

    @field_validator("overview", "architecture_note")
    @classmethod
    def _cap(cls, value: str) -> str:
        return value.strip()[:700]


class PreferenceProposal(BaseModel):
    intent: str = "preference"
    scope: str
    action: str = "set"
    value: Any = None
    reason: str = ""
    confidence: float = 0.0
    requires_confirmation: bool = True

    @field_validator("scope")
    @classmethod
    def _scope(cls, value: str) -> str:
        if value not in ALLOWED_SCOPES:
            raise ValueError(f"ámbito no permitido: {value}")
        return value

    @field_validator("action")
    @classmethod
    def _action(cls, value: str) -> str:
        if value not in ("set", "add", "remove"):
            raise ValueError(f"acción no permitida: {value}")
        return value


class PreferenceClassification(BaseModel):
    intent: str = "question"
    confidence: float = 0.0


def _extract_json(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise InvalidModelOutput(
            "la respuesta del modelo no contiene JSON",
            hint="revisa el modelo o baja la temperatura",
        )
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise InvalidModelOutput(
            f"JSON inválido del modelo: {exc.msg}",
            hint="se intentará una vez más con la plantilla determinista",
        ) from exc
    if not isinstance(data, dict):
        raise InvalidModelOutput("el JSON del modelo no es un objeto")
    return data


def parse_prose(raw: str) -> ProsePayload:
    return ProsePayload.model_validate(_extract_json(raw))


def parse_proposal(raw: str) -> PreferenceProposal:
    return PreferenceProposal.model_validate(_extract_json(raw))


def filter_notes(payload: ProsePayload, facts: dict) -> ProsePayload:
    """Descarta notas que apunten a rutas inexistentes en los hechos."""
    known = {module.get("path") for module in facts.get("modules", [])}
    payload.module_notes = [note for note in payload.module_notes if note.path in known]
    return payload


def prose_schema_hint() -> str:
    return json.dumps(
        {
            "overview": "string (máx. 700)",
            "architecture_note": "string (máx. 700)",
            "module_notes": [{"path": "ruta existente", "purpose": "1 frase"}],
            "confidence": "0..1",
            "asks": ["string"],
        },
        ensure_ascii=False,
    )
