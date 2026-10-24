"""Paleta y utilidades de presentación."""

from __future__ import annotations

import os
import sys

PRIMARY = "#F23078"
DEEP = "#8C0B47"
SECONDARY = "#ADA4BF"
SUCCESS = "#98D979"
BACKGROUND = "#0D0D0D"

PALETTE = {
    "primary": PRIMARY,
    "deep": DEEP,
    "secondary": SECONDARY,
    "success": SUCCESS,
    "bg": BACKGROUND,
}


def color_enabled() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("TERM", "").lower() in ("dumb", ""):
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def use_rich() -> bool:
    try:
        import rich  # noqa: F401

        return True
    except ImportError:
        return False


def styled() -> bool:
    """Rich solo cuando hay terminal real: evita romper al redirigir la salida."""
    return use_rich() and sys.stdout.isatty()


def supports_unicode() -> bool:
    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    return "utf" in encoding


def write(text: str) -> None:
    """Escribe texto literal (sin markup) tolerando consolas cp1252."""
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.write(text.encode(encoding, "replace").decode(encoding))
    sys.stdout.flush()


def console():
    from rich.console import Console

    return Console(highlight=False, soft_wrap=False)


def style(name: str) -> str:
    return PALETTE.get(name, PRIMARY)


def badge(text: str, kind: str = "primary") -> str:
    return f"[bold {style(kind)}]{text}[/bold {style(kind)}]"
