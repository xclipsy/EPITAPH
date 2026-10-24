"""Avisos estructurados de la TUI."""

from __future__ import annotations

from ..llm.health import OllamaHealth
from .theme import DEEP, PRIMARY, SECONDARY, SUCCESS, console, use_rich


def ollama_notice(
    health: OllamaHealth,
    *,
    command: str,
    model: str,
    deterministic: str | None = "epitaph update --no-llm",
) -> None:
    """Panel de error cuando el servicio local no puede atender la petición."""
    title = (
        "ERROR · OLLAMA NO DISPONIBLE"
        if not health.reachable
        else "ERROR · SIN MODELOS LOCALES"
    )

    if not use_rich():
        print(f"[!] {title}")
        print(f"  estado:   {health.state}")
        print(f"  endpoint: {health.base_url}")
        print(f"  comando:  {command}")
        print(f"  modelo:   {model}")
        if health.error:
            print(f"  causa:    {health.error}")
        if not health.reachable:
            print("  solución: ollama serve")
        print(f"  solución: ollama pull {model}")
        print("  diagnóstico: epitaph doctor")
        if deterministic:
            print(f"  alternativa: {deterministic}")
        return

    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    details = Table.grid(padding=(0, 2))
    details.add_column(style=SECONDARY, no_wrap=True)
    details.add_column(style="bold white")
    details.add_row("estado", f"[bold {PRIMARY}]{health.state.upper()}[/bold {PRIMARY}]")
    details.add_row("endpoint", health.base_url)
    details.add_row("comando", command)
    details.add_row("modelo", model)
    if health.error:
        details.add_row("causa", health.error)

    steps = Table.grid(padding=(0, 2))
    steps.add_column(style=f"bold {SUCCESS}", no_wrap=True)
    steps.add_column(style="white")
    if not health.reachable:
        steps.add_row("1.", "ollama serve")
        steps.add_row("2.", f"ollama pull {model}")
        steps.add_row("3.", "epitaph doctor")
    else:
        steps.add_row("1.", f"ollama pull {model}")
        steps.add_row("2.", "epitaph doctor")

    parts = [
        Text(
            "EPITAPH necesita el servicio local para generar prosa y conversar.",
            style="white",
        ),
        Text(""),
        details,
        Text(""),
        Text("Solución", style=f"bold {SUCCESS}"),
        steps,
    ]
    if deterministic:
        alternative = Text()
        alternative.append("Alternativa determinista\n", style=f"bold {SECONDARY}")
        alternative.append(f"  {deterministic}", style=f"bold {SUCCESS}")
        parts.extend([Text(""), alternative])

    body = Group(*parts)
    console().print(
        Panel(
            body,
            title=f"[bold {PRIMARY}]{title}[/bold {PRIMARY}]",
            border_style=PRIMARY,
            expand=False,
        )
    )


def ollama_hint(health: OllamaHealth, *, model: str) -> None:
    """Aviso compacto para el chat cuando el servicio deja de responder."""
    if not health.reachable:
        headline = "Ollama no está disponible"
        action = "ollama serve"
    else:
        headline = "Ollama está activo pero no hay modelos"
        action = f"ollama pull {model}"

    if use_rich():
        console().print(
            f"[bold {PRIMARY}]{headline}[/bold {PRIMARY}] "
            f"[{SECONDARY}]({health.base_url})[/{SECONDARY}]\n"
            f"[{SECONDARY}]siguiente paso:[/] [bold {SUCCESS}]{action}[/bold {SUCCESS}]"
        )
        return
    print(f"{headline} ({health.base_url}).")
    print(f"Siguiente paso: `{action}`.")


def doctor_table(rows: list[tuple[str, str, str]]) -> None:
    """Tabla de diagnóstico con el mismo lenguaje visual que los avisos."""
    if not use_rich():
        for name, state, detail in rows:
            print(f"{name:<12} {state:<16} {detail}")
        return

    from rich.table import Table

    table = Table(
        title="Diagnóstico de EPITAPH",
        border_style=DEEP,
        header_style=f"bold {PRIMARY}",
        expand=False,
    )
    table.add_column("Componente", style=SECONDARY, no_wrap=True)
    table.add_column("Estado", style="bold white", no_wrap=True)
    table.add_column("Detalle", style="white")
    for name, state, detail in rows:
        table.add_row(name, state, detail)
    console().print(table)
