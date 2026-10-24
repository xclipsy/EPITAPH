"""Tablas y paneles de la TUI."""

from __future__ import annotations

from .components import tip
from .theme import PRIMARY, SECONDARY, SUCCESS, console, use_rich


def models_table(models: list[dict], active: str = "", hardware=None) -> None:
    if not models:
        if use_rich():
            from rich.panel import Panel

            console().print(
                Panel(
                    f"[{SECONDARY}]No hay modelos instalados en Ollama.[/{SECONDARY}]\n"
                    f"[bold {SUCCESS}]epitaph models pull qwen2.5-coder:3b[/bold {SUCCESS}]",
                    title=f"[bold {PRIMARY}]SIN MODELOS LOCALES[/bold {PRIMARY}]",
                    border_style=PRIMARY,
                    expand=False,
                )
            )
        else:
            print("No hay modelos instalados. Usa `epitaph models pull qwen2.5-coder:3b`.")
        return
    if not use_rich():
        for model in models:
            name = model.get("name", "?")
            size = round((model.get("size") or 0) / 1024**3, 1)
            marker = "*" if name == active else " "
            print(f"{marker} {name:<32} {size:>5} GB")
        return

    from rich.table import Table

    from ..llm.hardware import estimate_ram_gb, estimate_tokens_per_second, viable

    table = Table(
        title=f"[bold {PRIMARY}]Modelos locales · Ollama[/bold {PRIMARY}]",
        border_style=PRIMARY,
        header_style=f"bold {PRIMARY}",
        expand=True,
    )
    table.add_column("Modelo", style="bold white", no_wrap=True)
    table.add_column("Params", style=SECONDARY, justify="right")
    table.add_column("Quant", style=SECONDARY, justify="right")
    table.add_column("Disco", style=SECONDARY, justify="right")
    table.add_column("RAM", style=SECONDARY, justify="right")
    table.add_column("tok/s*", style=SECONDARY, justify="right")
    table.add_column("Estado", justify="center", no_wrap=True)

    blocked: list[tuple[str, str]] = []
    for model in models:
        name = model.get("name", "?")
        details = model.get("details", {}) or {}
        size = round((model.get("size") or 0) / 1024**3, 2)
        ram = estimate_ram_gb(model)
        speed = estimate_tokens_per_second(model, hardware) if hardware else 0.0
        ok, reason = viable(model, hardware) if hardware else (True, "")
        if name == active:
            status = f"[bold {SUCCESS}]ACTIVO[/bold {SUCCESS}]"
        elif not ok:
            status = f"[bold {PRIMARY}]NO VIABLE[/bold {PRIMARY}]"
            blocked.append((name, reason))
        else:
            status = f"[{SECONDARY}]disponible[/{SECONDARY}]"
        table.add_row(
            name,
            str(details.get("parameter_size", "?")),
            str(details.get("quantization_level", "?")),
            f"{size:.1f} GB",
            f"{ram:.1f} GB",
            f"{speed:.0f}",
            status,
        )

    console().print(table)
    if blocked:
        details = "; ".join(f"{name} ({reason})" for name, reason in blocked)
        tip(f"no viables en este equipo: {details}")
    tip("estimación para este equipo; usa `epitaph bench` para medir")


def facts_panel(facts: dict) -> None:
    totals = facts.get("totals", {})
    languages = ", ".join(item["name"] for item in facts.get("languages", [])[:4]) or "—"
    if not use_rich():
        print(
            f"{facts.get('name')}: {totals.get('files', 0)} archivos, "
            f"{totals.get('loc', 0)} LOC, {languages}"
        )
        return

    from rich.panel import Panel

    body = (
        f"[bold {PRIMARY}]{facts.get('name', 'proyecto')}[/bold {PRIMARY}]\n"
        f"[{SECONDARY}]archivos:[/] {totals.get('files', 0)} · "
        f"[{SECONDARY}]LOC:[/] {totals.get('loc', 0)} · "
        f"[{SECONDARY}]funciones:[/] {totals.get('functions', 0)} · "
        f"[{SECONDARY}]clases:[/] {totals.get('classes', 0)}\n"
        f"[{SECONDARY}]lenguajes:[/] {languages}\n"
        f"[{SECONDARY}]mantenibilidad media:[/] {totals.get('avg_maintainability', 0)}/100 · "
        f"[{SECONDARY}]complejidad media:[/] {totals.get('avg_cyclomatic', 0)}\n"
        f"[{SECONDARY}]ciclos:[/] {len(facts.get('cycles', []))} · "
        f"[{SECONDARY}]huérfanos:[/] {len(facts.get('orphans', []))} · "
        f"[{SECONDARY}]secretos:[/] {len(facts.get('secrets', []))}"
    )
    console().print(
        Panel(
            body,
            border_style=PRIMARY,
            title=f"[bold {PRIMARY}]Análisis del proyecto[/bold {PRIMARY}]",
        )
    )
