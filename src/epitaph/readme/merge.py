"""Fusión no destructiva del README."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

from .markers import Segment, fingerprint, format_block, parse


@dataclass
class MergeResult:
    text: str
    changed: bool
    changes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    suggested: str | None = None


def merge(
    existing: str | None,
    sections: OrderedDict[str, str],
    *,
    title: str | None = None,
    reorder: bool = False,
) -> MergeResult:
    if existing is None or not existing.strip():
        text = _build_new(sections, title or "Proyecto")
        return MergeResult(
            text=text,
            changed=True,
            changes=[f"creado: {section_id}" for section_id in sections],
        )

    parsed = parse(existing)
    if parsed.errors:
        suggested = _build_new(sections, title or _existing_title(existing) or "Proyecto")
        return MergeResult(
            text=existing,
            changed=False,
            errors=parsed.errors,
            suggested=suggested,
        )

    existing_auto = {
        segment.id: segment for segment in parsed.segments if segment.kind == "auto" and segment.id
    }

    changes: list[str] = []
    notes: list[str] = []

    # Reordenar solo es seguro si el documento no tiene contenido humano.
    has_human_text = any(
        segment.kind == "text" and segment.raw.strip() for segment in parsed.segments
    )
    if reorder:
        if has_human_text:
            notes.append(
                "El README contiene texto humano: se conserva el orden y se omite el reordenado."
            )
        else:
            rebuilt = _build_new(sections, title or _existing_title(existing) or "Proyecto")
            return MergeResult(
                text=rebuilt,
                changed=rebuilt != existing,
                changes=["reordenadas las secciones"],
            )

    output: list[str] = []
    for segment in parsed.segments:
        if segment.kind == "text":
            output.append(segment.raw)
            continue

        assert segment.id is not None
        new_content = sections.get(segment.id)
        if new_content is None:
            # Sección eliminada de la configuración: se conserva tal cual.
            output.append(segment.raw)
            continue

        if fingerprint(new_content) == fingerprint(segment.content):
            output.append(segment.raw)
            continue

        output.append(format_block(segment.id, new_content))
        changes.append(f"actualizada: {segment.id}")

    missing = [sid for sid in sections if sid not in existing_auto]
    if missing:
        for sid in missing:
            changes.append(f"añadida: {sid}")
        tail = "\n\n".join(format_block(sid, sections[sid]) for sid in missing)
        prefix = "\n".join(output).rstrip("\n")
        output = [f"{prefix}\n\n{tail}" if prefix.strip() else tail]

    text = "\n".join(output)
    if not text.endswith("\n"):
        text += "\n"

    if not changes and not notes:
        return MergeResult(text=existing, changed=False)

    return MergeResult(text=text, changed=text != existing, changes=changes, notes=notes)


def _build_new(sections: OrderedDict[str, str], title: str) -> str:
    parts = [f"# {title}", ""]
    for section_id, content in sections.items():
        parts.append(format_block(section_id, content))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _existing_title(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def section_map(text: str) -> dict[str, Segment]:
    parsed = parse(text)
    return {
        segment.id: segment for segment in parsed.segments if segment.kind == "auto" and segment.id
    }
