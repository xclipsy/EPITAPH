"""Banner de EPITAPH con degradado y degradación elegante."""

from __future__ import annotations

import time

from .theme import BACKGROUND, DEEP, PRIMARY, color_enabled

ART = r"""
███████╗██████╗ ██╗████████╗ █████╗ ██████╗ ██╗  ██╗
██╔════╝██╔══██╗██║╚══██╔══╝██╔══██╗██╔══██╗██║  ██║
█████╗  ██████╔╝██║   ██║   ███████║██████╔╝███████║
██╔══╝  ██╔═══╝ ██║   ██║   ██╔══██║██╔═══╝ ██╔══██║
███████╗██║     ██║   ██║   ██║  ██║██║     ██║  ██║
╚══════╝╚═╝     ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝
""".strip("\n").splitlines()

TAGLINE = "documentación viva · inferencia local · no destructiva"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def _blend(start: str, end: str, ratio: float) -> str:
    a = _hex_to_rgb(start)
    b = _hex_to_rgb(end)
    mixed = tuple(round(a[i] + (b[i] - a[i]) * ratio) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def show(animate: bool | None = None, model: str = "", tier: str = "") -> None:
    if not color_enabled():
        print("\n".join(ART))
        print(TAGLINE)
        if model:
            print(f"modelo: {model} ({tier})" if tier else f"modelo: {model}")
        return

    try:
        from rich.console import Console
        from rich.text import Text

        console = Console(highlight=False)
        animate = animate if animate is not None else True
        for index, line in enumerate(ART):
            ratio = index / max(len(ART) - 1, 1)
            text = Text(line, style=f"bold {_blend(PRIMARY, DEEP, ratio)}")
            console.print(text)
            if animate:
                time.sleep(0.03)
        console.print(Text(f"  {TAGLINE}", style=SECONDARY_COLOR))
        if model:
            suffix = f"{model} · {tier}" if tier else model
            console.print(Text(f"  modelo: {suffix}", style=SECONDARY_COLOR))
        console.print()
    except ImportError:
        print("\n".join(ART))


SECONDARY_COLOR = "#ADA4BF"
BACKGROUND_COLOR = BACKGROUND


def compact() -> str:
    return f"EPITAPH · {TAGLINE}"
