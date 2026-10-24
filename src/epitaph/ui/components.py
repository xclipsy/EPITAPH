"""Componentes visuales compartidos: paneles, tablas y tips.

Sigue el lenguaje de la CLI de PRAXIA (Panel para bloques, Table para
catálogos, Rule para enmarcar la entrada y tips al pie), con la paleta de
EPITAPH.
"""

from __future__ import annotations

from typing import Any

from .theme import DEEP, PRIMARY, SECONDARY, SUCCESS, console, use_rich

# --------------------------------------------------------------------- tips


def tip(text: str) -> None:
    """Sugerencia breve al pie de una tabla o panel."""
    if use_rich():
        console().print(f"[{SECONDARY}]-> Tip:[/] [{SECONDARY}]{text}[/]")
    else:
        print(f"-> Tip: {text}")


def rule() -> None:
    """Línea horizontal de la paleta para enmarcar la entrada."""
    if not use_rich():
        return
    from rich.rule import Rule

    console().print(Rule(style=PRIMARY))


# ------------------------------------------------------------------- paneles


def info_panel(
    body: Any,
    *,
    title: str = "",
    border: str = PRIMARY,
    expand: bool = False,
) -> None:
    if not use_rich():
        print(_plain(body))
        return
    from rich.panel import Panel

    console().print(
        Panel(
            body,
            title=f"[bold {border}]{title}[/bold {border}]" if title else None,
            border_style=border,
            expand=expand,
        )
    )


def kv_panel(
    title: str,
    rows: list[tuple[str, Any]],
    *,
    border: str = PRIMARY,
    footer: str = "",
) -> None:
    """Panel de pares clave/valor alineados."""
    if not use_rich():
        print(title)
        for key, value in rows:
            print(f"  {key}: {_plain(value)}")
        if footer:
            print(footer)
        return

    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style=SECONDARY, no_wrap=True)
    grid.add_column(style="bold white")
    for key, value in rows:
        grid.add_row(key, value)

    parts: list[Any] = [grid]
    if footer:
        parts.extend([Text(""), Text(footer, style=SECONDARY)])

    console().print(
        Panel(
            Group(*parts),
            title=f"[bold {border}]{title}[/bold {border}]",
            border_style=border,
            expand=False,
        )
    )


def error_panel(message: str, hint: str | None = None) -> None:
    if not use_rich():
        print(f"✖ {message}")
        if hint:
            print(f"  Acción: {hint}")
        return

    from rich.panel import Panel
    from rich.text import Text

    body = Text(message, style="bold white")
    if hint:
        body.append("\n\n")
        body.append("Acción  ", style=f"bold {SUCCESS}")
        body.append(hint, style="white")

    console().print(
        Panel(
            body,
            title=f"[bold {PRIMARY}]ERROR[/bold {PRIMARY}]",
            border_style=PRIMARY,
            expand=False,
        )
    )


def syntax_panel(title: str, code: str, *, lexer: str = "text") -> None:
    if not use_rich():
        print(code)
        return
    from rich.panel import Panel
    from rich.syntax import Syntax

    console().print(
        Panel(
            Syntax(code, lexer, theme="monokai", line_numbers=False, word_wrap=True),
            title=f"[bold {PRIMARY}]{title}[/bold {PRIMARY}]",
            border_style=DEEP,
            expand=True,
        )
    )


def diff_panel(title: str, diff: str, *, lexer: str = "diff") -> None:
    syntax_panel(title, diff, lexer=lexer)


# ------------------------------------------------------------------- tablas


def catalog_table(
    title: str,
    columns: list[str],
    rows: list[tuple[Any, ...]],
    *,
    border: str = PRIMARY,
    footer: str = "",
) -> None:
    if not use_rich():
        print(title)
        for row in rows:
            print("  " + "  ".join(_plain(cell) for cell in row))
        if footer:
            print(footer)
        return

    from rich.table import Table

    table = Table(
        title=f"[bold {PRIMARY}]{title}[/bold {PRIMARY}]",
        border_style=border,
        header_style=f"bold {PRIMARY}",
        expand=False,
    )
    for index, column in enumerate(columns):
        table.add_column(column, style="bold white" if index == 0 else SECONDARY)
    for row in rows:
        table.add_row(*(str(cell) for cell in row))
    console().print(table)
    if footer:
        tip(footer)


# ------------------------------------------------------------------ respuestas


def answer_title(model: str, tier: str = "") -> str:
    suffix = f" · {tier}" if tier else ""
    return f"[bold {PRIMARY}]EPITAPH ({model}{suffix} · local)[/bold {PRIMARY}]"


def answer_renderable(text: str, *, model: str, tier: str = "", spinner: bool = False) -> Any:
    """Panel de respuesta; con ``spinner`` añade el marco de espera de PRAXIA."""
    from rich.console import Group
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.spinner import Spinner
    from rich.text import Text

    body = (
        Markdown(text)
        if text.strip()
        else Text("Iniciando generación de tokens…", style=SECONDARY)
    )
    panel = Panel(body, title=answer_title(model, tier), border_style=PRIMARY)
    if not spinner:
        return panel

    line = Text("─" * (console().width or 80), style=PRIMARY)
    wait = Spinner(
        "dots",
        text=Text(f" pensando · {model} · 100% local", style=f"bold {PRIMARY}"),
    )
    return Group(panel, line, wait, line)


def answer_panel(text: str, *, model: str, tier: str = "") -> None:
    if not use_rich():
        print(text)
        return
    console().print(answer_renderable(text, model=model, tier=tier))


# ------------------------------------------------------------------- helpers


def _plain(value: Any) -> str:
    if isinstance(value, str):
        import re

        return re.sub(r"\[/?[^\]]+\]", "", value)
    return str(value)
