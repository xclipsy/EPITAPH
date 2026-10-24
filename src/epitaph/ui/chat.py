"""Chat interactivo en terminal con comandos y preferencias en lenguaje natural."""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

from .. import __version__, pipeline, requirements, safety, suggestions
from ..analyzers import analyze
from ..config import Config, dumps
from ..errors import EpitaphError
from ..llm.hardware import detect as detect_hardware
from ..llm.health import probe
from ..llm.prompts import build_question_messages
from ..llm.provider_ollama import OllamaProvider
from ..llm.roles import installed_names, resolve_model
from ..preferences import (
    PreferenceStore,
    apply_to_config,
    build,
    conflicts,
    detect,
    resolve,
    validate,
)
from ..preferences.apply import directives_text
from ..scheduler.trigger import parse_spec
from ..state import State
from . import banner
from .notices import doctor_table, ollama_hint, ollama_notice
from .tables import facts_panel, models_table
from .theme import PRIMARY, SECONDARY, SUCCESS, console, use_rich

HELP = """
Comandos disponibles
  /help                 esta ayuda
  /status               estado del proyecto y del planificador
  /update [--dry]       analiza y actualiza la documentación
  /diff                 muestra el diff pendiente del README
  /undo                 restaura el último backup del README
  /suggestions          genera suggestions.md
  /requirements         analiza dependencias y muestra el diff
  /models               lista modelos locales
  /model <nombre>       fija el modelo global
  /every <cadencia>     on_save | interval:5 | idle:10 | manual
  /pause /resume        pausa o reanuda los runs automáticos
  /prefs [add|rm|clear] gestiona preferencias
  /structure [reset]    muestra o restablece la estructura del README
  /permissions          muestra la matriz de permisos
  /config               muestra la configuración actual
  /doctor               diagnóstico del entorno
  /clear                limpia la pantalla
  /exit                 salir

También puedes escribir en lenguaje natural:
  «prefiero el árbol al final y sin badges»
  «sugiere modularización por dominio, no por capas»
  «¿por qué hay un ciclo entre a y b?»
"""


class ChatSession:
    def __init__(self, root: Path, config: Config, state: State | None = None) -> None:
        self.root = Path(root).resolve()
        self.config = config
        self.state = state or State.load(self.root)
        self.provider = OllamaProvider(config.llm.base_url)
        self.store = PreferenceStore.for_root(
            self.root,
            config.preferences.path,
            max_items=config.preferences.max_directives,
        )
        self.last_update = None

    # ------------------------------------------------------------------ loop

    def run(self) -> int:
        banner.show(animate=self.config.ui.animations)
        self._print(
            f"[{SECONDARY}]proyecto:[/] {self.config.project_name(self.root)} · "
            f"modelo: {self.config.llm.roles.writer} · cadencia: {self.config.trigger.default}\n"
        )
        self._print("Escribe /help para ver los comandos.\n")

        while True:
            try:
                line = self._read()
            except (KeyboardInterrupt, EOFError):
                self._print("\nSaliendo.")
                return 0
            if line is None:
                return 0
            line = line.strip()
            if not line:
                continue
            try:
                if not self.handle(line):
                    return 0
            except EpitaphError as exc:
                self._print(f"[red]{exc.render()}[/red]" if use_rich() else exc.render())
            except Exception as exc:  # noqa: BLE001
                self._print(f"[red]error inesperado: {exc}[/red]" if use_rich() else str(exc))

    def _read(self) -> str | None:
        if not sys.stdin.isatty():
            line = sys.stdin.readline()
            return line if line else None
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.styles import Style

            if not hasattr(self, "_pt"):
                self._pt = PromptSession(
                    style=Style.from_dict({"prompt": f"{PRIMARY} bold"}),
                )
            return self._pt.prompt([("class:prompt", "> ")])
        except ImportError:
            return input("> ")

    # -------------------------------------------------------------- dispatch

    def handle(self, line: str) -> bool:
        command, _, argument = line.partition(" ")
        command = command.lower()
        argument = argument.strip()

        if command in ("/exit", "/quit"):
            self._print("Saliendo.")
            return False
        if command in ("/help", "?"):
            self._print(HELP)
            return True
        if command == "/clear":
            print("\033[2J\033[H", end="")
            return True
        if command == "/status":
            self._status()
            return True
        if command == "/update":
            self._update(dry_run="--dry" in argument)
            return True
        if command == "/diff":
            self._diff()
            return True
        if command == "/undo":
            self._undo()
            return True
        if command == "/suggestions":
            self._suggestions()
            return True
        if command == "/requirements":
            self._requirements()
            return True
        if command == "/models":
            self._models()
            return True
        if command == "/model":
            self._model(argument)
            return True
        if command == "/every":
            self._every(argument)
            return True
        if command == "/pause":
            self.state.paused = True
            self.state.save(self.root)
            self._print("Planificador en pausa.")
            return True
        if command == "/resume":
            self.state.paused = False
            self.state.save(self.root)
            self._print("Planificador reanudado.")
            return True
        if command == "/prefs":
            self._prefs(argument)
            return True
        if command == "/structure":
            self._structure(argument)
            return True
        if command == "/permissions":
            self._permissions()
            return True
        if command == "/config":
            self._config()
            return True
        if command == "/doctor":
            self._doctor()
            return True

        # lenguaje natural
        return self._natural(line)

    # ------------------------------------------------------------- commands

    def _status(self) -> None:
        facts = analyze(self.root)
        facts_panel(facts)
        self._print(
            f"[{SECONDARY}]cadencia:[/] {self.config.trigger.default} · "
            f"[{SECONDARY}]pausado:[/] {self.state.paused} · "
            f"[{SECONDARY}]último run:[/] {self.state.last_run or '—'}"
        )
        self._print(
            f"[{SECONDARY}]preferencias:[/] {len(self.store.items)} · "
            f"[{SECONDARY}]config:[/] {Config.path_for(self.root)}"
        )

    def _update(self, dry_run: bool = False) -> None:
        verdict = safety.check(self.config, "write:readme")
        auto = False
        if not dry_run and verdict == "ask":
            if not self._confirm("¿Escribir el README cuando haya cambios?"):
                self._print("Cancelado.")
                return
            auto = True
        if verdict == "deny" and not dry_run:
            self._print("Permiso denegado para escribir el README (/permissions).")
            return

        self._print("Analizando y generando…")
        result = pipeline.update(
            self.root,
            self.config,
            self.state,
            provider=self.provider,
            use_llm=True,
            dry_run=dry_run,
            auto_approve=auto,
        )
        self.last_update = result
        if result.merge and result.merge.changes:
            for change in result.merge.changes:
                self._print(f"  · {change}")
        if result.skipped_reason:
            self._print(f"[{SECONDARY}]{result.skipped_reason}[/]")
        if result.written:
            self._print(
                f"[{SUCCESS}]✔ README actualizado[/] en {result.duration_ms} ms · "
                f"{len(result.merge.changes) if result.merge else 0} secciones"
            )
        if result.merge and result.merge.errors:
            for error in result.merge.errors:
                self._print(f"[red]marcador: {error}[/red]")
        if result.merge and result.merge.notes:
            for note in result.merge.notes:
                self._print(f"[{SECONDARY}]{note}[/]")

    def _diff(self) -> None:
        result = self.last_update
        if result is None or result.merge is None:
            self._print("No hay cambios pendientes. Usa /update --dry.")
            return
        path = self.root / self.config.readme.path
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        diff = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                result.merge.text.splitlines(keepends=True),
                fromfile="README.md (actual)",
                tofile="README.md (propuesto)",
            )
        )
        self._print(diff or "Sin diferencias.")

    def _undo(self) -> None:
        backups = safety.list_backups(self.root, "README.md")
        if not backups:
            self._print("No hay backups del README.")
            return
        latest = backups[0]
        if not self._confirm(f"¿Restaurar {latest.name}?"):
            return
        safety.restore(latest, self.root / self.config.readme.path)
        safety.log(self.root, "undo:readme", backup=str(latest))
        self._print(f"Restaurado desde {latest.name}")

    def _suggestions(self) -> None:
        facts = analyze(self.root)
        deps = requirements.analyze(self.root, facts, self.config)
        items = suggestions.build(facts, deps, self.root)
        effective = resolve(self.config, self.store.items)
        path, selected, hidden_prefs, hidden_status = suggestions.write_report(
            self.root, self.config, items, effective
        )
        self._print(f"{len(selected)} sugerencias escritas en {path.name}")
        if hidden_prefs or hidden_status:
            self._print(
                f"[{SECONDARY}]{hidden_prefs} ocultas por preferencias · "
                f"{hidden_status} descartadas antes[/]"
            )

    def _requirements(self) -> None:
        facts = analyze(self.root)
        result = requirements.analyze(self.root, facts, self.config)
        diff = requirements.render_diff(self.root, self.config, result)
        self._print(diff or "Sin diferencias: las dependencias coinciden.")
        if result["missing"]:
            target = requirements.write_suggested(self.root, self.config, result)
            self._print(f"Propuesta escrita en {target.name}")

    def _models(self) -> None:
        hw = detect_hardware()
        health = probe(self.provider)
        if not health.reachable:
            ollama_notice(
                health,
                command="/models",
                model=self.config.llm.roles.writer,
                deterministic="epitaph update --no-llm",
            )
            return
        try:
            models = self.provider.list_models()
        except EpitaphError as exc:
            self._print(exc.render())
            return
        models_table(models, active=self.config.llm.roles.writer, hardware=hw)

    def _model(self, name: str) -> None:
        if not name:
            self._print(f"Modelo actual: {self.config.llm.roles.writer}")
            return
        for role in ("summarizer", "writer", "advisor", "chat"):
            setattr(self.config.llm.roles, role, name)
        self.config.save(self.root)
        self._print(f"Modelo global: {name}")

    def _every(self, value: str) -> None:
        if not value:
            self._print(f"Cadencia actual: {self.config.trigger.default}")
            return
        try:
            spec = parse_spec(value)
        except ValueError as exc:
            self._print(str(exc))
            return
        self.config.trigger.default = spec.as_string()
        self.config.save(self.root)
        self._print(f"Cadencia: {spec.label}")

    def _prefs(self, argument: str) -> None:
        action, _, rest = argument.partition(" ")
        action = action.strip().lower()
        rest = rest.strip()

        if action == "add" and rest:
            self._propose(rest)
            return
        if action == "rm" and rest:
            if self.store.remove(rest):
                self._print(f"Preferencia {rest} eliminada.")
            else:
                self._print(f"No existe {rest}.")
            return
        if action == "clear":
            if self._confirm("¿Eliminar todas las preferencias?"):
                self.store.clear()
                self._print("Preferencias eliminadas.")
            return
        if action in ("why",) and rest:
            preference = self.store.get(rest)
            if preference is None:
                self._print("No existe.")
                return
            self._print(
                f"{preference.id} · {preference.scope} = {preference.value}\n"
                f"origen: {preference.origin} · {preference.created_at}\n"
                f"nota: {preference.note or '—'}"
            )
            return

        if not self.store.items:
            self._print("No hay preferencias. Escribe una frase o usa /prefs add <texto>.")
            return
        for preference in self.store.items:
            self._print(
                f"  {preference.id}  {preference.scope:<24} "
                f"{str(preference.value)[:60]:<62} [{preference.origin}]"
            )
        effective = resolve(self.config, self.store.items)
        self._print(f"\n[{SECONDARY}]directivas activas:[/]\n{directives_text(effective)}")

    def _structure(self, argument: str) -> None:
        if argument.strip().lower() == "reset":
            self.store.items = [
                item for item in self.store.items if item.scope != "readme.structure"
            ]
            self.store.save()
            self.config.readme.sections = list(Config.default().readme.sections)
            self.config.save(self.root)
            self._print("Estructura restablecida.")
            return
        effective = resolve(self.config, self.store.items)
        self._print("Estructura efectiva del README:")
        for index, section in enumerate(effective.sections, start=1):
            self._print(f"  {index}. {section}")
        if effective.sections != self.config.readme.sections:
            self._print(f"[{SECONDARY}]modificada por preferencias[/]")

    def _permissions(self) -> None:
        for action in (
            "write:readme",
            "write:requirements",
            "write:suggestions",
            "write:code",
        ):
            self._print(f"  {action:<22} {safety.check(self.config, action)}")

    def _config(self) -> None:
        self._print(f"Ruta: {Config.path_for(self.root)}\n")
        self._print(dumps(self.config.model_dump(mode="python")))

    def _doctor(self) -> None:
        import platform

        hw = detect_hardware()
        health = probe(self.provider)
        clean, _ = safety.status(self.root)
        ok = f"[bold {SUCCESS}]OK[/bold {SUCCESS}]"
        rows = [
            ("epitaph", ok, __version__),
            ("python", ok, platform.python_version()),
            ("sistema", ok, f"{hw.system} {hw.machine} · {hw.cpu_count} hilos"),
            ("memoria", ok, f"{hw.ram_total_gb:.1f} GB ({hw.ram_available_gb:.1f} libres)"),
            (
                "gpu",
                f"[bold {SUCCESS}]DETECTADA[/bold {SUCCESS}]"
                if hw.gpu
                else f"[{SECONDARY}]SIN GPU[/{SECONDARY}]",
                hw.gpu or "inferencia en CPU",
            ),
            (
                "ollama",
                f"[bold {SUCCESS}]CONECTADO[/bold {SUCCESS}]"
                if health.reachable
                else f"[bold {PRIMARY}]NO DISPONIBLE[/bold {PRIMARY}]",
                health.base_url,
            ),
            (
                "modelos",
                f"[bold {SUCCESS}]{len(health.models)}[/bold {SUCCESS}]"
                if health.models
                else f"[bold {PRIMARY}]NINGUNO[/bold {PRIMARY}]",
                ", ".join(health.models) or f"ollama pull {self.config.llm.roles.writer}",
            ),
            (
                "git",
                f"[bold {SUCCESS}]LIMPIO[/bold {SUCCESS}]"
                if clean
                else f"[bold {PRIMARY}]CON CAMBIOS[/bold {PRIMARY}]",
                "árbol de trabajo",
            ),
            ("config", ok, str(Config.path_for(self.root))),
        ]
        doctor_table(rows)

    # ------------------------------------------------------------- natural

    def _natural(self, line: str) -> bool:
        detection = detect(line)
        if detection.is_preference:
            if self._propose(line):
                return True

        health = probe(self.provider)
        if not health.ready:
            ollama_hint(health, model=self.config.llm.roles.chat)
            return True

        try:
            facts = analyze(self.root)
            models = installed_names(self.provider.list_models())
            model = resolve_model("chat", self.config, models)
            answer = self.provider.chat(
                model,
                build_question_messages(line, facts),
                num_ctx=self.config.llm.params.num_ctx,
                num_predict=250,
                temperature=0.2,
            )
            self._print(answer.strip())
            return True
        except EpitaphError as exc:
            self._print(exc.render())

        self._print(
            "No entendí esa petición. Usa /help, o formula una preferencia "
            "como «prefiero el árbol al final y sin badges»."
        )
        return True

    def _propose(self, text: str) -> bool:
        proposal = build(text, detect(text).scope_hint, self.config, len(self.store.items))
        if proposal is None:
            self._print("No pude convertir eso en una preferencia concreta.")
            return False

        ok, error = validate(proposal, self.config)
        if not ok:
            self._print(f"No se puede aplicar: {error}")
            return False

        notes = conflicts(proposal, self.store.items)
        self._print("\nPropuesta de preferencia:")
        self._print(f"  ámbito: {proposal.scope}")
        self._print(f"  valor:  {proposal.value}")
        if notes:
            for note in notes:
                self._print(f"  conflicto: {note}")

        if self.config.preferences.confirm_from_chat and not self._confirm("¿Guardar?"):
            self._print("Descartada.")
            return True

        preference = self.store.add(
            proposal.scope,
            proposal.value,
            note=proposal.reason,
            origin="chat",
        )
        safety.log(self.root, "preference:add", id=preference.id, scope=preference.scope)
        self._print(f"Guardada como {preference.id}.")

        effective = resolve(self.config, self.store.items)
        updated = apply_to_config(self.config, effective)
        self.config.readme = updated.readme
        self.config.project.output_language = updated.project.output_language
        self.config.save(self.root)
        self._print("Se aplicará en el próximo update.")
        return True

    # -------------------------------------------------------------- helpers

    def _confirm(self, prompt: str) -> bool:
        if not sys.stdin.isatty():
            return False
        answer = input(f"{prompt} [s/N]: ").strip().lower()
        return answer in ("s", "si", "sí", "y", "yes")

    def _print(self, text: str) -> None:
        if use_rich():
            console().print(text)
        else:
            print(text)
