"""Componentes visuales compartidos: paneles, tablas y tips.

Sigue el lenguaje de la CLI de PRAXIA (Panel para bloques, Table para
catálogos, Rule para enmarcar la entrada y tips al pie), con la paleta de
EPITAPH.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .theme import DEEP, PRIMARY, SECONDARY, SUCCESS, console, use_rich

# Directorios y extensiones comunes para el explorador estilo Praxia
IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".epitaph",
}

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "bash",
    ".rs": "rust",
    ".go": "go",
    ".sql": "sql",
}

# ----------------------------------------------------------- ghost text auto-suggest
try:
    from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion

    class SlashCommandAutoSuggest(AutoSuggest):
        """Genera sugerencias en sombreado (ghost text) mientras el usuario escribe en terminal."""

        def __init__(self, commands: list[str]) -> None:
            self.commands = sorted(commands)

        def get_suggestion(self, buffer, document):
            text = document.text_before_cursor
            if not text:
                return None
            if text.startswith("/"):
                for cmd in self.commands:
                    if cmd.startswith(text) and cmd != text:
                        return Suggestion(cmd[len(text) :])
            return None

except ImportError:
    SlashCommandAutoSuggest = None  # type: ignore[assignment, misc]

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


# ----------------------------------------------------------- explorador estilo Praxia


def build_rich_tree(
    dir_path: Path,
    current_tree: Any,
    max_depth: int = 3,
    current_depth: int = 0,
) -> None:
    """Construye un árbol jerárquico Rich con colores y extensiones tipo Praxia."""
    if current_depth > max_depth:
        return
    try:
        entries = sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except Exception:
        return

    for entry in entries:
        if entry.name in IGNORED_DIRECTORIES or entry.name.startswith("."):
            continue
        if entry.is_dir():
            branch = current_tree.add(f"[bold {DEEP}][dir] {entry.name}[/bold {DEEP}]")
            build_rich_tree(entry, branch, max_depth, current_depth + 1)
        else:
            ext = entry.suffix.lower()
            lang = EXTENSION_TO_LANGUAGE.get(ext, "file")
            current_tree.add(
                f"[bold white][file] {entry.name}[/bold white] [{SECONDARY}]({lang})[/{SECONDARY}]"
            )


def resolve_file(repo_root: Path, file_str: str) -> Path | None:
    """Resuelve la ruta de un archivo tanto si es relativa como si es solo el nombre."""
    file_str = file_str.strip().strip("'\"")
    direct = (repo_root / file_str).resolve()
    if direct.exists() and direct.is_file():
        return direct

    target_name = Path(file_str).name
    try:
        for f in repo_root.rglob(target_name):
            if f.is_file() and not any(
                part in IGNORED_DIRECTORIES or part.startswith(".") for part in f.parts
            ):
                return f
        lower_name = target_name.lower()
        for f in repo_root.rglob("*"):
            if f.is_file() and not any(
                part in IGNORED_DIRECTORIES or part.startswith(".") for part in f.parts
            ):
                if f.name.lower() == lower_name:
                    return f
    except Exception:
        pass
    return None


def view_file_in_terminal(
    file_path: Path,
    highlight_range: tuple[int, int] | None = None,
    func_name: str | None = None,
    repo_root: Path | None = None,
) -> None:
    """Muestra el visor de código con números de línea y resaltado de sintaxis estilo Praxia."""
    if not file_path.exists() or not file_path.is_file():
        console().print(f"[bold {PRIMARY}]Archivo no encontrado:[/] {file_path}")
        return

    ext = file_path.suffix.lower()
    lang = EXTENSION_TO_LANGUAGE.get(ext, "python")

    display_name = file_path.name
    if repo_root:
        try:
            display_name = str(file_path.relative_to(repo_root)).replace("\\", "/")
        except ValueError:
            display_name = file_path.name

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        total_lines = len(lines)

        if func_name and not highlight_range:
            for idx, line in enumerate(lines):
                if re.search(rf"\bdef\s+{re.escape(func_name)}\b", line) or re.search(
                    rf"\bfunction\s+{re.escape(func_name)}\b", line
                ):
                    highlight_range = (idx + 1, min(total_lines, idx + 25))
                    break

        if highlight_range:
            start_l = max(1, highlight_range[0])
            end_l = min(total_lines, highlight_range[1])
            l_range = (max(1, start_l - 4), min(total_lines, end_l + 10))
            h_lines = set(range(start_l, end_l + 1))
            title_extra = f" | Líneas {start_l}-{end_l} de {total_lines}"
        elif total_lines > 60:
            l_range = (1, 60)
            h_lines = None
            title_extra = f" | Vista preliminar (Líneas 1-60 de {total_lines})"
        else:
            l_range = None
            h_lines = None
            title_extra = f" | {total_lines} líneas"

        if func_name:
            title_extra += f" | Función: {func_name}"

        if not use_rich():
            print(f"--- {display_name}{title_extra} ---")
            print(content[:2000])
            return

        from rich.panel import Panel
        from rich.syntax import Syntax

        syntax = Syntax(
            content,
            lang,
            line_numbers=True,
            theme="monokai",
            highlight_lines=h_lines,
            line_range=l_range,
        )
        console().print(
            Panel(
                syntax,
                title=f"[bold {PRIMARY}][file] {display_name}{title_extra} ({lang})[/bold {PRIMARY}]",
                border_style=PRIMARY,
            )
        )

        if not highlight_range and total_lines > 60:
            console().print(
                f"[{SECONDARY}]Mostrando líneas 1-60 de {total_lines}. "
                f"Usa [bold white]/view {display_name} 61 120[/bold white] para continuar leyendo.[/{SECONDARY}]"
            )
    except Exception as exc:
        console().print(f"[bold {PRIMARY}]Error al leer archivo:[/] {exc}")


def display_metrics_table(facts: dict, repo_root: Path | None = None) -> None:
    """Muestra la tabla de métricas generales de calidad y salud del código estilo Praxia."""
    totals = facts.get("totals", {})
    languages = facts.get("languages", [])
    cycles = facts.get("cycles", [])
    secrets = facts.get("secrets", [])
    orphans = facts.get("orphans", [])

    if not use_rich():
        print("Métricas Generales de Calidad (EPITAPH Engine):")
        print(f"  MI: {totals.get('avg_maintainability', 0):.1f}/100")
        print(f"  CC: {totals.get('avg_cyclomatic', 0):.2f}")
        print(f"  Archivos: {totals.get('files', 0)} · LOC: {totals.get('loc', 0)}")
        return

    from rich.table import Table

    table = Table(
        title=f"[bold {PRIMARY}]Métricas Generales de Calidad (EPITAPH Engine)[/bold {PRIMARY}]",
        border_style=PRIMARY,
    )
    table.add_column("Criterio / Métrica", style=f"bold {PRIMARY}", no_wrap=True)
    table.add_column("Valor Obtenido", style="bold white")
    table.add_column("Estado / Diagnóstico", style="bold")

    avg_mi = float(totals.get("avg_maintainability", 75.0))
    mi_status = (
        f"[bold {SUCCESS}]ÓPTIMO[/bold {SUCCESS}]"
        if avg_mi >= 65
        else "[yellow]ALERTA[/yellow]"
        if avg_mi >= 50
        else f"[bold {PRIMARY}]CRÍTICO[/bold {PRIMARY}]"
    )
    table.add_row("Índice de Mantenibilidad (MI)", f"{avg_mi:.1f} / 100", mi_status)

    avg_cc = float(totals.get("avg_cyclomatic", 2.0))
    cc_status = (
        f"[bold {SUCCESS}]BAJO[/bold {SUCCESS}]"
        if avg_cc <= 5
        else "[yellow]MEDIO[/yellow]"
        if avg_cc <= 10
        else f"[bold {PRIMARY}]ALTO[/bold {PRIMARY}]"
    )
    table.add_row("Complejidad Ciclomática Media (CC)", f"{avg_cc:.2f}", cc_status)

    loc = totals.get("loc", 0)
    files = totals.get("files", 0)
    fns = totals.get("functions", 0)
    cls_cnt = totals.get("classes", 0)
    table.add_row(
        "Volumen de Código",
        f"{files} archivos · {loc} LOC",
        f"[{SECONDARY}]{fns} funciones · {cls_cnt} clases[/{SECONDARY}]",
    )

    cycles_cnt = len(cycles)
    cycles_status = (
        f"[bold {SUCCESS}]ÓPTIMO (0 ciclos)[/bold {SUCCESS}]"
        if cycles_cnt == 0
        else f"[bold {PRIMARY}]ALERTA ({cycles_cnt} ciclos)[/bold {PRIMARY}]"
    )
    table.add_row(
        "Dependencias Circulares",
        f"{cycles_cnt} ciclos detectados",
        cycles_status,
    )

    orphans_cnt = len(orphans)
    orphans_status = (
        f"[bold {SUCCESS}]LIMPIO[/bold {SUCCESS}]"
        if orphans_cnt == 0
        else f"[yellow]{orphans_cnt} huérfanos[/yellow]"
    )
    table.add_row(
        "Módulos Huérfanos / Dead Code",
        f"{orphans_cnt} módulos",
        orphans_status,
    )

    secrets_cnt = len(secrets)
    secrets_status = (
        f"[bold {SUCCESS}]SEGURO (0)[/bold {SUCCESS}]"
        if secrets_cnt == 0
        else f"[bold {PRIMARY}]RIESGO ({secrets_cnt} detectados)[/bold {PRIMARY}]"
    )
    table.add_row(
        "Escaneo de Secretos / Credenciales",
        f"{secrets_cnt} detectados",
        secrets_status,
    )

    langs_list = []
    for lang_item in languages[:4]:
        if isinstance(lang_item, dict):
            pct = lang_item.get("percentage")
            pct_str = f" ({pct:.0f}%)" if pct is not None else ""
            langs_list.append(f"{lang_item.get('name', '?')}{pct_str}")
        else:
            langs_list.append(str(lang_item))
    langs_str = ", ".join(langs_list) or "—"
    table.add_row(
        "Lenguajes Detectados",
        langs_str,
        f"[{SECONDARY}]{len(languages)} detectados[/{SECONDARY}]",
    )

    console().print(table)


# ------------------------------------------------------------------- helpers


def _plain(value: Any) -> str:
    if isinstance(value, str):
        import re

        return re.sub(r"\[/?[^\]]+\]", "", value)
    return str(value)
