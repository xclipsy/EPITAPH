"""Banner de EPITAPH con degradado, panel y degradación elegante."""

from __future__ import annotations

import time
from typing import Any

from .theme import BACKGROUND, DEEP, PRIMARY, SECONDARY, color_enabled, console, use_rich

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


def _metadata(model: str, tier: str, project: str) -> str:
    engine = "Ollama / llama.cpp"
    if model:
        engine = f"{model} [{tier}]" if tier else model
    parts = ["100% local", engine, "sin telemetría"]
    if project:
        parts.insert(0, project)
    return " · ".join(parts)


def _body(count: int | None, *, model: str, tier: str, project: str) -> Any:
    from rich.console import Group
    from rich.text import Text

    lines = ART if count is None else ART[:count]
    art = Text()
    for index, line in enumerate(lines):
        ratio = index / max(len(ART) - 1, 1)
        art.append(line, style=f"bold {_blend(PRIMARY, DEEP, ratio)}")
        art.append("\n")

    tagline = Text(f"  {TAGLINE}", style=SECONDARY)
    parts: list[Any] = [art, tagline]

    metadata = _metadata(model, tier, project)
    if metadata:
        parts.extend([Text(""), Text(f"  {metadata}", style=f"bold {SECONDARY}")])
    return Group(*parts)


def show(
    animate: bool | None = None,
    model: str = "",
    tier: str = "",
    project: str = "",
) -> None:
    if not color_enabled() or not use_rich():
        print("\n".join(ART))
        print(TAGLINE)
        metadata = _metadata(model, tier, project)
        if metadata:
            print(metadata)
        return

    from rich.live import Live
    from rich.panel import Panel

    con = console()
    animate = animate if animate is not None else True

    if animate:
        with Live(console=con, refresh_per_second=30, transient=True) as live:
            for count in range(1, len(ART) + 1):
                live.update(
                    Panel(
                        _body(count, model=model, tier=tier, project=project),
                        border_style=PRIMARY,
                        expand=False,
                        padding=(0, 2),
                    )
                )
                time.sleep(0.03)

    con.print(
        Panel(
            _body(None, model=model, tier=tier, project=project),
            border_style=PRIMARY,
            expand=False,
            padding=(0, 2),
        )
    )


SECONDARY_COLOR = SECONDARY
BACKGROUND_COLOR = BACKGROUND


def compact() -> str:
    return f"EPITAPH · {TAGLINE}"
