"""Marcadores de secciones generadas y fingerprints."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

BEGIN_RE = re.compile(r"^\s*<!--\s*epitaph:begin\s+(?P<attrs>[^>]*?)\s*-->\s*$")
END_RE = re.compile(r"^\s*<!--\s*epitaph:end\s+id=(?P<id>[\w.-]+)\s*-->\s*$")
ATTR_RE = re.compile(r"([\w-]+)=([^\s]+)")


@dataclass
class Segment:
    kind: str  # "text" | "auto"
    raw: str
    id: str | None = None
    fp: str = ""
    content: str = ""


@dataclass
class ParseResult:
    segments: list[Segment] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ids(self) -> list[str]:
        return [segment.id for segment in self.segments if segment.kind == "auto" and segment.id]


def fingerprint(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()[:12]


def format_block(section_id: str, content: str) -> str:
    fp = fingerprint(content)
    return (
        f"<!-- epitaph:begin id={section_id} fp={fp} -->\n"
        f"{content.strip()}\n"
        f"<!-- epitaph:end id={section_id} -->"
    )


def parse(text: str) -> ParseResult:
    lines = text.split("\n")
    result = ParseResult()
    buffer: list[str] = []
    seen: set[str] = set()

    def flush() -> None:
        if buffer:
            result.segments.append(Segment(kind="text", raw="\n".join(buffer)))
            buffer.clear()

    i = 0
    while i < len(lines):
        begin = BEGIN_RE.match(lines[i])
        if not begin:
            buffer.append(lines[i])
            i += 1
            continue

        attrs = dict(ATTR_RE.findall(begin.group("attrs")))
        section_id = attrs.get("id")
        if not section_id:
            result.errors.append(f"marcador sin id en la línea {i + 1}")
            buffer.append(lines[i])
            i += 1
            continue

        depth = 0
        end_index: int | None = None
        j = i + 1
        while j < len(lines):
            if BEGIN_RE.match(lines[j]):
                depth += 1
            end = END_RE.match(lines[j])
            if end and end.group("id") == section_id:
                if depth == 0:
                    end_index = j
                    break
                depth -= 1
            j += 1

        if end_index is None:
            result.errors.append(f"bloque '{section_id}' sin cierre (línea {i + 1})")
            buffer.append(lines[i])
            i += 1
            continue

        if section_id in seen:
            result.errors.append(f"id duplicado: '{section_id}' (línea {i + 1})")
        seen.add(section_id)

        flush()
        content = "\n".join(lines[i + 1 : end_index])
        result.segments.append(
            Segment(
                kind="auto",
                raw="\n".join(lines[i : end_index + 1]),
                id=section_id,
                fp=attrs.get("fp", ""),
                content=content,
            )
        )
        i = end_index + 1

    flush()
    return result
