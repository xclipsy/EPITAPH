"""Wizard de primera ejecución estilo Praxia CLI."""

from __future__ import annotations

import sys
from pathlib import Path

from ..config import Config
from ..llm.hardware import detect
from ..llm.provider_ollama import OllamaProvider
from ..llm.roles import installed_names
from ..scheduler.trigger import parse_spec
from ..state import State
from .theme import PRIMARY, SECONDARY, console, use_rich


class WizardResult(tuple):
    """Resultado del asistente: (root, config). Permite desempaquetar o acceder por atributo."""

    def __new__(cls, root: Path, config: Config):
        return super().__new__(cls, (root, config))

    @property
    def root(self) -> Path:
        return self[0]

    @property
    def config(self) -> Config:
        return self[1]


def run(
    root: Path,
    config: Config | None = None,
    non_interactive: bool = False,
) -> WizardResult:
    root = Path(root).resolve()

    _say("\n[bold]Vamos a configurar EPITAPH para tu proyecto.[/bold]\n")

    # 1. Selección de carpeta de trabajo (Workspace)
    if not non_interactive:
        if use_rich() and sys.stdin.isatty():
            from rich.table import Table

            target_table = Table(
                title=f"[bold {PRIMARY}]Selección de Carpeta de Trabajo (Workspace)[/bold {PRIMARY}]",
                border_style=PRIMARY,
                show_header=False,
            )
            target_table.add_column("Opción", style=f"bold {PRIMARY}", width=4)
            target_table.add_column("Tipo", style="bold white", width=22)
            target_table.add_column("Descripción", style=SECONDARY)
            target_table.add_row(
                "1",
                "Directorio Actual",
                f"Trabajar en la carpeta actual ({root.name})",
            )
            target_table.add_row(
                "2",
                "Ruta Personalizada",
                "Ingresar la ruta absoluta o relativa de la carpeta del proyecto",
            )
            console().print(target_table)
        else:
            _say("Selección de Carpeta de Trabajo:")
            _say(f"  [1] Directorio Actual ({root.name})")
            _say("  [2] Ruta Personalizada")

        target_choice = _ask("Selecciona el tipo de directorio [1/2]", "1", non_interactive)
        if target_choice == "2":
            while True:
                path_input = _ask(
                    "Ingresa la ruta de la carpeta de trabajo del proyecto",
                    str(root),
                    non_interactive,
                ).strip()
                if not path_input:
                    break
                candidate = Path(path_input).expanduser().resolve()
                if not candidate.exists():
                    if _yes(
                        f"La carpeta '{candidate}' no existe. ¿Deseas crearla?",
                        True,
                        non_interactive,
                    ):
                        try:
                            candidate.mkdir(parents=True, exist_ok=True)
                            root = candidate
                            break
                        except Exception as exc:
                            _say(f"Error al crear la carpeta: {exc}")
                            continue
                    else:
                        _say("Por favor ingresa una ruta existente.")
                        continue
                if not candidate.is_dir():
                    _say(f"Error: '{candidate}' no es un directorio.")
                    continue
                root = candidate
                break

    cfg = config or Config.load_or_default(root)
    cfg.project.name = _ask(
        "Nombre del proyecto", cfg.project.name or root.name, non_interactive
    )

    # 2. Funciones a activar
    _say("\n[bold]Funciones principales:[/bold]")
    cfg.features.readme = _yes("  · README auto escalable", True, non_interactive)
    cfg.features.requirements = _yes(
        "  · Requerimientos (requirements.txt) auto escalable", True, non_interactive
    )
    cfg.features.suggestions = _yes(
        "  · Informe de sugerencias arquitectónicas (suggestions.md)",
        True,
        non_interactive,
    )

    # 3. Temporizadores / Cadencia
    if use_rich():
        from rich.table import Table

        timer_table = Table(
            title=f"[bold {PRIMARY}]Frecuencia de Actualización / Temporizadores[/bold {PRIMARY}]",
            border_style=PRIMARY,
            show_header=False,
        )
        timer_table.add_column("Opción", style=f"bold {PRIMARY}", width=4)
        timer_table.add_column("Modo", style="bold white", width=22)
        timer_table.add_column("Descripción", style=SECONDARY)
        timer_table.add_row(
            "1",
            "on_autosave",
            "Cada vez que se haga autosave (guardado automático del editor)",
        )
        timer_table.add_row(
            "2",
            "on_save",
            "Cada vez que se haga save (guardado manual)",
        )
        timer_table.add_row("3", "interval:1", "Cada 1 minuto")
        timer_table.add_row("4", "interval:5", "Cada 5 minutos (recomendado)")
        timer_table.add_row("5", "interval:10", "Cada 10 minutos")
        timer_table.add_row("6", "interval:30", "Cada 30 minutos")
        timer_table.add_row("7", "idle:5", "Por inactividad tras cambios (5 minutos)")
        timer_table.add_row("8", "manual", "Solo manual (/update o epitaph update)")
        timer_table.add_row("9", "personalizado", "Especificar otro intervalo en minutos")
        console().print(timer_table)
    else:
        _say("\n¿Cada cuánto quieres que EPITAPH analice el proyecto?")
        _say("  [1] Cada vez que se haga autosave (guardado automático del editor)")
        _say("  [2] Cada vez que se haga save (guardado manual)")
        _say("  [3] Cada 1 minuto")
        _say("  [4] Cada 5 minutos (recomendado)")
        _say("  [5] Cada 10 minutos")
        _say("  [6] Cada 30 minutos")
        _say("  [7] Por inactividad tras cambios (5 minutos)")
        _say("  [8] Solo manual (/update)")
        _say("  [9] Otro valor personalizado")

    choice = _ask("Opción de cadencia", "4", non_interactive)
    cadence = {
        "1": "on_autosave",
        "2": "on_save",
        "3": "interval:1",
        "4": "interval:5",
        "5": "interval:10",
        "6": "interval:30",
        "7": "idle:5",
        "8": "manual",
    }.get(choice, "")
    if not cadence:
        value = _ask("Minutos entre análisis", "5", non_interactive)
        try:
            cadence = parse_spec(f"interval:{value}").as_string()
        except ValueError:
            cadence = "interval:5"
    cfg.trigger.default = cadence

    # 4. Hardware e Inferencia
    hw = detect()
    _say(
        f"\nHardware detectado: {hw.cpu_count} hilos · {hw.ram_total_gb:.1f} GB RAM "
        f"({hw.ram_available_gb:.1f} GB libres)"
        + (f" · GPU: {hw.gpu}" if hw.gpu else " · sin GPU dedicada")
    )

    provider = OllamaProvider(cfg.llm.base_url)
    models = []
    if provider.is_available():
        try:
            raw_models = provider.list_models()
            models = installed_names(raw_models)
            if models and use_rich():
                from .tables import models_table

                models_table(raw_models, active=cfg.llm.roles.writer, hardware=hw)
        except Exception:
            models = []

    if models:
        _say("Modelos disponibles: " + ", ".join(models))
        suggested = _pick_model(models)
        chosen = _ask("Modelo para redacción y chat", suggested, non_interactive)
        if chosen in models:
            cfg.llm.roles.writer = chosen
            cfg.llm.roles.advisor = chosen
            cfg.llm.roles.chat = chosen
            cfg.llm.roles.summarizer = _pick_light(models) or chosen
    else:
        _say("No se detectaron modelos en Ollama. Puedes descargar uno después con:")
        _say("  epitaph models pull qwen2.5-coder:3b")

    # 5. Permisos de escritura
    _say("\nPermisos de escritura del README:")
    _say("  [1] Preguntar antes de escribir (recomendado)")
    _say("  [2] Permitir siempre automáticamente")
    _say("  [3] Solo lectura (denegar escritura automática)")
    permission = {"1": "ask", "2": "allow", "3": "deny"}.get(
        _ask("Opción de permisos", "1", non_interactive), "ask"
    )
    cfg.permissions.write_readme = permission

    # Guardar configuración y estado en la carpeta de trabajo seleccionada
    cfg.save(root)
    state = State.load(root)
    state.wizard_completed = True
    state.save(root)

    _say(f"\nConfiguración guardada en: {Config.path_for(root)}")
    _say(f"Carpeta de trabajo: [bold white]{root}[/bold white]")
    _say(f"Cadencia configurada: [bold white]{cfg.trigger.default}[/bold white]\n")

    return WizardResult(root, cfg)


def _pick_model(models: list[str]) -> str:
    for needle in ("qwen2.5-coder:3b", "qwen2.5-coder:1.5b", "qwen2.5-coder:7b"):
        if needle in models:
            return needle
    return models[0]


def _pick_light(models: list[str]) -> str:
    for model in models:
        if "1.5b" in model:
            return model
    return models[0]


def _ask(prompt: str, default: str, non_interactive: bool) -> str:
    if non_interactive or not sys.stdin.isatty():
        return default
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw or default


def _yes(prompt: str, default: bool, non_interactive: bool) -> bool:
    if non_interactive or not sys.stdin.isatty():
        return default
    raw = input(f"{prompt} [{'S/n' if default else 's/N'}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("s", "si", "sí", "y", "yes")


def _say(text: str) -> None:
    if use_rich():
        from .theme import console

        console().print(text, style=SECONDARY if not text.startswith("\n") else "")
    else:
        print(text)
