"""Wizard de primera ejecución."""

from __future__ import annotations

import sys
from pathlib import Path

from ..config import Config
from ..llm.hardware import detect
from ..llm.provider_ollama import OllamaProvider
from ..llm.roles import installed_names
from ..scheduler.trigger import parse_spec
from ..state import State
from .theme import SECONDARY, use_rich


def run(root: Path, config: Config | None = None, non_interactive: bool = False) -> Config:
    root = Path(root).resolve()
    cfg = config or Config.default(root.name)

    _say("\nVamos a configurar EPITAPH para este proyecto.\n")

    cfg.project.name = _ask("Nombre del proyecto", cfg.project.name or root.name, non_interactive)

    _say("\nFunciones:")
    cfg.features.readme = _yes("  · README automático", True, non_interactive)
    cfg.features.requirements = _yes("  · Dependencias sugeridas", True, non_interactive)
    cfg.features.suggestions = _yes("  · Informe de sugerencias", True, non_interactive)

    _say("\n¿Cada cuánto quieres que EPITAPH analice el proyecto?")
    _say("  [1] Por cada guardado")
    _say("  [2] Cada 1 minuto")
    _say("  [3] Cada 5 minutos (recomendado)")
    _say("  [4] Cada 10 minutos")
    _say("  [5] Cada 30 minutos")
    _say("  [6] Solo manual (/update)")
    _say("  [7] Otro valor")
    choice = _ask("Opción", "3", non_interactive)
    cadence = {
        "1": "on_save",
        "2": "interval:1",
        "3": "interval:5",
        "4": "interval:10",
        "5": "interval:30",
        "6": "manual",
    }.get(choice, "")
    if not cadence:
        value = _ask("Minutos entre análisis", "5", non_interactive)
        try:
            cadence = parse_spec(f"interval:{value}").as_string()
        except ValueError:
            cadence = "interval:5"
    cfg.trigger.default = cadence

    hw = detect()
    _say(
        f"\nHardware: {hw.cpu_count} hilos · {hw.ram_total_gb:.1f} GB RAM "
        f"({hw.ram_available_gb:.1f} GB libres)"
        + (f" · GPU: {hw.gpu}" if hw.gpu else " · sin GPU dedicada")
    )

    provider = OllamaProvider(cfg.llm.base_url)
    models = []
    if provider.is_available():
        try:
            models = installed_names(provider.list_models())
        except Exception:
            models = []
    if models:
        _say("Modelos instalados: " + ", ".join(models))
        suggested = _pick_model(models)
        chosen = _ask("Modelo para redactar", suggested, non_interactive)
        if chosen in models:
            cfg.llm.roles.writer = chosen
            cfg.llm.roles.advisor = chosen
            cfg.llm.roles.chat = chosen
            cfg.llm.roles.summarizer = _pick_light(models) or chosen
    else:
        _say("No se detectaron modelos en Ollama. Puedes descargar uno después con:")
        _say("  epitaph models pull qwen2.5-coder:3b")

    _say("\nPermisos de escritura del README:")
    _say("  [1] Preguntar antes de escribir (recomendado)")
    _say("  [2] Permitir siempre")
    _say("  [3] Denegar")
    permission = {"1": "ask", "2": "allow", "3": "deny"}.get(
        _ask("Opción", "1", non_interactive), "ask"
    )
    cfg.permissions.write_readme = permission

    cfg.save(root)
    state = State.load(root)
    state.wizard_completed = True
    state.save(root)

    _say(f"\nConfiguración guardada en {Config.path_for(root)}")
    _say(f"Cadencia: {cfg.trigger.default}\n")
    return cfg


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
