"""Presupuesto de contexto."""

from __future__ import annotations


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def truncate(text: str, max_tokens: int) -> str:
    limit = max_tokens * 4
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit("\n", 1)[0] + "\n…"


def fit(pieces: list[str], max_tokens: int) -> str:
    """Une fragmentos recortando desde el final hasta caber en el presupuesto."""
    selected: list[str] = []
    used = 0
    for piece in pieces:
        cost = approx_tokens(piece)
        if used + cost <= max_tokens:
            selected.append(piece)
            used += cost
        else:
            remaining = max_tokens - used
            if remaining > 40:
                selected.append(truncate(piece, remaining))
            break
    return "\n\n".join(selected)
