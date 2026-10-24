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


def console():
    from rich.console import Console

    return Console(highlight=False, soft_wrap=False)


def style(name: str) -> str:
    return PALETTE.get(name, PRIMARY)


def badge(text: str, kind: str = "primary") -> str:
    return f"[bold {style(kind)}]{text}[/bold {style(kind)}]"
