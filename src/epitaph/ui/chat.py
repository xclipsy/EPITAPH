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
from .components import (
    answer_panel,
    answer_renderable,
    catalog_table,
    diff_panel,
    error_panel,
    info_panel,
    kv_panel,
    rule,
    syntax_panel,
    tip,
)
from .notices import doctor_table, ollama_hint, ollama_notice
from .tables import facts_panel, models_table
from .theme import PRIMARY, SECONDARY, SUCCESS, console, use_rich

COMMANDS = (
    "/help",
    "/status",
    "/update",
    "/diff",
    "/undo",
    "/suggestions",
    "/requirements",
    "/models",
    "/model",
    "/every",
    "/pause",
    "/resume",
    "/prefs",
    "/structure",
    "/permissions",
    "/config",
    "/doctor",
    "/clear",
    "/exit",
)

HELP_ROWS = [
    ("/help", "Muestra esta guía y los atajos", "/help o ayuda"),
    ("/status", "Estado del proyecto y del planificador", "/status"),
    ("/update [--dry]", "Analiza y actualiza el README", "/update --dry"),
    ("/diff", "Diff pendiente del último análisis", "/diff"),
    ("/undo", "Restaura el último backup del README", "/undo"),
    ("/suggestions", "Genera el informe de sugerencias", "/suggestions"),
    ("/requirements", "Analiza dependencias y propone cambios", "/requirements"),
    ("/models", "Lista los modelos locales de Ollama", "/models"),
    ("/model <nombre>", "Fija el modelo global", "/model qwen2.5-coder:3b"),
    ("/every <cadencia>", "Cambia la cadencia de actualización", "/every interval:10"),
    ("/pause · /resume", "Pausa o reanuda los runs automáticos", "/pause"),
    ("/prefs [add|rm|clear]", "Gestiona preferencias del README", "/prefs add tono informal"),
    ("/structure [reset]", "Muestra o restablece la estructura", "/structure reset"),
    ("/permissions", "Matriz de permisos de escritura", "/permissions"),
    ("/config", "Configuración efectiva del proyecto", "/config"),
    ("/doctor", "Diagnóstico del entorno y de Ollama", "/doctor"),
    ("/clear", "Limpia la pantalla", "/clear"),
    ("/exit", "Cierra la sesión", "/exit o salir"),
]


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
        banner.show(
            animate=self.config.ui.animations,
            model=self.config.llm.roles.writer,
            project=self.config.project_name(self.root),
        )
        self._intro()

        while True:
            try:
                line = self._read()
            except (KeyboardInterrupt, EOFError):
                self._print("")
                self._print(f"[{SECONDARY}]Sesión cerrada.[/]")
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
                error_panel(exc.message, exc.hint)
            except Exception as exc:  # noqa: BLE001
                error_panel(f"error inesperado: {exc}", "revisa `epitaph doctor`")

    def _intro(self) -> None:
        hw = detect_hardware()
        model = self.config.llm.roles.writer
        chat_model = self.config.llm.roles.chat
        models = model if chat_model == model else f"{model} · chat: {chat_model}"
        body = (
            f"[bold {PRIMARY}]Documentación viva, local y no destructiva[/bold {PRIMARY}]\n"
            f"[{SECONDARY}]proyecto:[/] {self.config.project_name(self.root)} · "
            f"[{SECONDARY}]modelo:[/] [bold white]{models}[/bold white] · "
            f"[{SECONDARY}]cadencia:[/] {self.config.trigger.default}\n"
            f"[{SECONDARY}]hardware:[/] {hw.system} {hw.machine} · "
            f"{hw.cpu_count} hilos · {hw.ram_total_gb:.1f} GB · "
            f"{hw.gpu or 'CPU'}\n\n"
            "[white]Analizo el repositorio y mantengo el README sincronizado con el código.[/white]\n"
            f"[{SECONDARY}]Escribe [bold white]/help[/bold white] para ver los comandos, "
            "o formula una preferencia en lenguaje natural.[/]"
        )
        info_panel(
            body,
            title=f"EPITAPH · {model} · local",
            border=PRIMARY,
        )
        tip(
            "prueba «prefiero el árbol al final y sin badges» o "
            "«¿qué hace este proyecto?»"
        )

    def _read(self) -> str | None:
        if not sys.stdin.isatty():
            line = sys.stdin.readline()
            return line if line else None
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
            from prompt_toolkit.completion import WordCompleter
            from prompt_toolkit.history import InMemoryHistory
            from prompt_toolkit.styles import Style

            if not hasattr(self, "_pt"):
                self._pt = PromptSession(
                    completer=WordCompleter(COMMANDS, ignore_case=True, match_middle=False),
                    auto_suggest=AutoSuggestFromHistory(),
                    complete_while_typing=True,
                    history=InMemoryHistory(),
                    style=Style.from_dict(
                        {
                            "prompt": f"{PRIMARY} bold",
                            "completion-menu.completion": f"bg:#1a1a1a {SECONDARY}",
                            "completion-menu.completion.current": f"bg:{PRIMARY} #0D0D0D",
                        }
                    ),
                )
            rule()
            line = self._pt.prompt([("class:prompt", "epitaph › ")])
            rule()
            return line
        except ImportError:
            return input("epitaph › ")

    # -------------------------------------------------------------- dispatch

    def handle(self, line: str) -> bool:
        command, _, argument = line.partition(" ")
        command = command.lower()
        argument = argument.strip()

        if command in ("/exit", "/quit", "salir", "exit"):
            self._print(f"[{SECONDARY}]Sesión cerrada.[/]")
            return False
        if command in ("/help", "?", "ayuda", "help"):
            self._help()
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
            info_panel(
                "Los runs automáticos quedan en pausa.",
                title="Planificador en pausa",
                border=SECONDARY,
            )
            tip("usa /resume para reanudarlos")
            return True
        if command == "/resume":
            self.state.paused = False
            self.state.save(self.root)
            info_panel(
                "Los runs automáticos vuelven a su cadencia.",
                title="Planificador reanudado",
                border=SUCCESS,
            )
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

    def _help(self) -> None:
        catalog_table(
            "Catálogo de comandos · EPITAPH",
            ["Comando", "Propósito", "Sintaxis / ejemplo"],
            HELP_ROWS,
            footer=(
                "también acepto lenguaje natural: «prefiero el árbol al final y sin "
                "badges», «sugiere modularización por dominio» o «¿por qué hay un "
                "ciclo entre a y b?»"
            ),
        )

    def _status(self) -> None:
        facts = analyze(self.root)
        facts_panel(facts)
        kv_panel(
            "Planificador y preferencias",
            [
                ("proyecto", self.config.project_name(self.root)),
                ("cadencia", self.config.trigger.default),
                ("pausado", "sí" if self.state.paused else "no"),
                ("último run", self.state.last_run or "—"),
                ("preferencias", str(len(self.store.items))),
                ("config", str(Config.path_for(self.root))),
            ],
            footer="usa /update --dry para revisar cambios sin escribir",
        )

    def _update(self, dry_run: bool = False) -> None:
        verdict = safety.check(self.config, "write:readme")
        auto = False
        if not dry_run and verdict == "ask":
            if not self._confirm("¿Escribir el README cuando haya cambios?"):
                info_panel("Actualización cancelada.", title="Sin cambios", border=SECONDARY)
                return
            auto = True
        if verdict == "deny" and not dry_run:
            error_panel(
                "Permiso denegado para escribir el README.",
                "revisa /permissions o .epitaph/config.toml",
            )
            return

        con = console()
        if use_rich() and con.is_terminal:
            with con.status(
                f"[bold {PRIMARY}]analizando y generando…[/bold {PRIMARY}]",
                spinner="dots",
            ):
                result = pipeline.update(
                    self.root,
                    self.config,
                    self.state,
                    provider=self.provider,
                    use_llm=True,
                    dry_run=dry_run,
                    auto_approve=auto,
                )
        else:
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
        self._render_update(result, dry_run)

    def _render_update(self, result, dry_run: bool) -> None:
        changes = result.merge.changes if result.merge else []
        if result.written:
            state = f"[bold {SUCCESS}]README actualizado[/bold {SUCCESS}]"
        elif result.skipped_reason:
            state = f"[{SECONDARY}]{result.skipped_reason}[/]"
        elif dry_run:
            state = f"[{SECONDARY}]dry-run · sin escritura[/]"
        else:
            state = f"[{SECONDARY}]sin cambios[/]"

        body: list[str] = [
            f"[{SECONDARY}]estado:[/] {state}",
            f"[{SECONDARY}]secciones:[/] {len(changes)} · "
            f"[{SECONDARY}]duraci\u00f3n:[/] {result.duration_ms} ms · "
            f"[{SECONDARY}]tokens:[/] {result.tokens_in} in / {result.tokens_out} out",
        ]
        if changes:
            body.append("")
            body.extend(f"[{SUCCESS}]·[/] {change}" for change in changes)
        if result.merge and result.merge.errors:
            body.append("")
            body.extend(f"[{PRIMARY}]marcador:[/] {error}" for error in result.merge.errors)

        info_panel(
            "\n".join(body),
            title="Actualización · README.md",
            border=SUCCESS if result.written else PRIMARY,
        )
        if result.merge and result.merge.notes:
            for note in result.merge.notes:
                tip(note)
        elif dry_run:
            tip("usa /update para escribir los cambios")

    def _diff(self) -> None:
        result = self.last_update
        if result is None or result.merge is None:
            info_panel(
                "No hay cambios pendientes.",
                title="Diff · README.md",
                border=SECONDARY,
            )
            tip("usa /update --dry para generar una propuesta")
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
        if not diff:
            info_panel("Sin diferencias.", title="Diff · README.md", border=SECONDARY)
            return
        diff_panel("Diff propuesto · README.md", diff)

    def _undo(self) -> None:
        backups = safety.list_backups(self.root, "README.md")
        if not backups:
            info_panel("No hay backups del README.", title="Undo", border=SECONDARY)
            return
        latest = backups[0]
        if not self._confirm(f"¿Restaurar {latest.name}?"):
            info_panel("Restauración cancelada.", title="Undo", border=SECONDARY)
            return
        safety.restore(latest, self.root / self.config.readme.path)
        safety.log(self.root, "undo:readme", backup=str(latest))
        info_panel(
            f"README restaurado desde [bold white]{latest.name}[/bold white].",
            title="Undo completado",
            border=SUCCESS,
        )

    def _suggestions(self) -> None:
        facts = analyze(self.root)
        deps = requirements.analyze(self.root, facts, self.config)
        items = suggestions.build(facts, deps, self.root)
        effective = resolve(self.config, self.store.items)
        path, selected, hidden_prefs, hidden_status = suggestions.write_report(
            self.root, self.config, items, effective
        )
        kv_panel(
            "Sugerencias generadas",
            [
                ("archivo", str(path.name)),
                ("incluidas", str(len(selected))),
                ("ocultas por preferencias", str(hidden_prefs)),
                ("descartadas antes", str(hidden_status)),
            ],
            border=SUCCESS,
            footer=f"revisa {path.name} antes de aplicarlo",
        )

    def _requirements(self) -> None:
        facts = analyze(self.root)
        result = requirements.analyze(self.root, facts, self.config)
        diff = requirements.render_diff(self.root, self.config, result)
        if diff:
            diff_panel("requirements.txt · propuesta", diff)
        else:
            info_panel(
                "Las dependencias declaradas coinciden.",
                title="requirements.txt",
                border=SUCCESS,
            )
        if result["missing"]:
            target = requirements.write_suggested(self.root, self.config, result)
            tip(f"propuesta escrita en {target.name}")

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
            error_panel(exc.message, exc.hint)
            return
        models_table(models, active=self.config.llm.roles.writer, hardware=hw)

    def _model(self, name: str) -> None:
        if not name:
            kv_panel(
                "Modelo activo",
                [
                    ("writer", self.config.llm.roles.writer),
                    ("summarizer", self.config.llm.roles.summarizer),
                    ("advisor", self.config.llm.roles.advisor),
                    ("chat", self.config.llm.roles.chat),
                ],
                footer="usa /model <nombre> para fijar uno global",
            )
            return
        for role in ("summarizer", "writer", "advisor", "chat"):
            setattr(self.config.llm.roles, role, name)
        self.config.save(self.root)
        info_panel(
            f"Todos los roles usan [bold white]{name}[/bold white].",
            title="Modelo global",
            border=SUCCESS,
        )

    def _every(self, value: str) -> None:
        if not value:
            kv_panel(
                "Cadencia activa",
                [("spec", self.config.trigger.default)],
                footer="valores: on_save · interval:5 · idle:10 · manual",
            )
            return
        try:
            spec = parse_spec(value)
        except ValueError as exc:
            error_panel(str(exc), "usa on_save, interval:N, idle:N o manual")
            return
        self.config.trigger.default = spec.as_string()
        self.config.save(self.root)
        info_panel(
            f"Cadencia: [bold white]{spec.label}[/bold white] "
            f"[{SECONDARY}]({spec.as_string()})[/]",
            title="Planificador",
            border=SUCCESS,
        )

    def _prefs(self, argument: str) -> None:
        action, _, rest = argument.partition(" ")
        action = action.strip().lower()
        rest = rest.strip()

        if action == "add" and rest:
            self._propose(rest)
            return
        if action == "rm" and rest:
            if self.store.remove(rest):
                info_panel(
                    f"Preferencia [bold white]{rest}[/bold white] eliminada.",
                    title="Preferencias",
                    border=SUCCESS,
                )
            else:
                error_panel(f"No existe la preferencia {rest}.")
            return
        if action == "clear":
            if self._confirm("¿Eliminar todas las preferencias?"):
                self.store.clear()
                info_panel("Preferencias eliminadas.", title="Preferencias", border=SUCCESS)
            return
        if action in ("why",) and rest:
            preference = self.store.get(rest)
            if preference is None:
                error_panel("No existe.")
                return
            kv_panel(
                f"Preferencia {preference.id}",
                [
                    ("ámbito", preference.scope),
                    ("valor", str(preference.value)),
                    ("origen", preference.origin),
                    ("creada", preference.created_at),
                    ("nota", preference.note or "—"),
                ],
            )
            return

        if not self.store.items:
            info_panel(
                "No hay preferencias guardadas.",
                title="Preferencias",
                border=SECONDARY,
            )
            tip("usa /prefs add <texto> o escribe una frase en lenguaje natural")
            return

        rows = [
            (
                preference.id,
                preference.scope,
                str(preference.value)[:60],
                preference.origin,
            )
            for preference in self.store.items
        ]
        catalog_table(
            "Preferencias guardadas",
            ["ID", "Ámbito", "Valor", "Origen"],
            rows,
        )
        effective = resolve(self.config, self.store.items)
        info_panel(
            directives_text(effective),
            title="Directivas activas",
            border=SECONDARY,
        )
        tip("usa /prefs why <id> para ver el detalle o /prefs rm <id> para eliminarla")

    def _structure(self, argument: str) -> None:
        if argument.strip().lower() == "reset":
            self.store.items = [
                item for item in self.store.items if item.scope != "readme.structure"
            ]
            self.store.save()
            self.config.readme.sections = list(Config.default().readme.sections)
            self.config.save(self.root)
            info_panel(
                "Estructura del README restablecida.",
                title="Estructura",
                border=SUCCESS,
            )
            return
        effective = resolve(self.config, self.store.items)
        rows = [(str(index), section) for index, section in enumerate(effective.sections, 1)]
        catalog_table("Estructura efectiva del README", ["#", "Sección"], rows)
        if effective.sections != self.config.readme.sections:
            tip("la estructura está modificada por preferencias; /structure reset la restaura")

    def _permissions(self) -> None:
        labels = {
            "allow": f"[bold {SUCCESS}]allow[/bold {SUCCESS}]",
            "ask": f"[bold {SECONDARY}]ask[/bold {SECONDARY}]",
            "deny": f"[bold {PRIMARY}]deny[/bold {PRIMARY}]",
        }
        descriptions = {
            "write:readme": "actualizar el README",
            "write:requirements": "escribir requirements.suggested.txt",
            "write:suggestions": "escribir suggestions.md",
            "write:code": "modificar código (solo v2)",
        }
        rows = [
            (action, labels.get(safety.check(self.config, action), "?"), descriptions[action])
            for action in descriptions
        ]
        catalog_table("Matriz de permisos", ["Acción", "Permiso", "Efecto"], rows)
        tip("los permisos se cambian solo en .epitaph/config.toml; el chat no puede concederlos")

    def _config(self) -> None:
        syntax_panel(
            "Configuración efectiva",
            dumps(self.config.model_dump(mode="python")),
            lexer="toml",
        )
        tip(f"archivo: {Config.path_for(self.root)}")

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
        if not health.ready:
            tip("inicia el servicio con `ollama serve` y descarga un modelo")

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
            answer = self._stream_answer(
                model,
                build_question_messages(line, facts),
            )
            if not answer.strip():
                info_panel(
                    "El modelo no devolvió texto.",
                    title="Respuesta vacía",
                    border=SECONDARY,
                )
                tip("prueba con otro modelo: /models y /model <nombre>")
            return True
        except EpitaphError as exc:
            error_panel(exc.message, exc.hint)
            tip("usa /help o formula una preferencia concreta")
        return True

    def _stream_answer(self, model: str, messages: list[dict]) -> str:
        options = {
            "num_ctx": self.config.llm.params.num_ctx,
            "num_predict": 250,
            "temperature": 0.2,
        }
        con = console()
        if not use_rich() or not con.is_terminal:
            answer = self.provider.chat(model, messages, **options)
            if answer.strip():
                answer_panel(answer, model=model)
            return answer

        from rich.live import Live

        chunks: list[str] = []

        def render(text: str):
            return answer_renderable(text, model=model, spinner=True)

        with Live(render(""), console=con, refresh_per_second=12, transient=True) as live:

            def on_token(token: str) -> None:
                chunks.append(token)
                live.update(render("".join(chunks)))

            answer = self.provider.chat(model, messages, on_token=on_token, **options)

        if answer.strip():
            answer_panel(answer, model=model)
        return answer

    def _propose(self, text: str) -> bool:
        proposal = build(text, detect(text).scope_hint, self.config, len(self.store.items))
        if proposal is None:
            error_panel(
                "No pude convertir eso en una preferencia concreta.",
                "sé más específico: ámbito y valor, por ejemplo «tono informal»",
            )
            return False

        ok, error = validate(proposal, self.config)
        if not ok:
            error_panel(f"No se puede aplicar: {error}")
            return False

        notes = conflicts(proposal, self.store.items)
        rows = [
            ("ámbito", proposal.scope),
            ("valor", str(proposal.value)),
            ("motivo", proposal.reason or "—"),
        ]
        for index, note in enumerate(notes, 1):
            rows.append((f"conflicto {index}", note))
        kv_panel("Propuesta de preferencia", rows)

        if self.config.preferences.confirm_from_chat and not self._confirm("¿Guardar?"):
            info_panel("Preferencia descartada.", title="Preferencias", border=SECONDARY)
            return True

        preference = self.store.add(
            proposal.scope,
            proposal.value,
            note=proposal.reason,
            origin="chat",
        )
        safety.log(self.root, "preference:add", id=preference.id, scope=preference.scope)

        effective = resolve(self.config, self.store.items)
        updated = apply_to_config(self.config, effective)
        self.config.readme = updated.readme
        self.config.project.output_language = updated.project.output_language
        self.config.save(self.root)
        info_panel(
            f"Guardada como [bold white]{preference.id}[/bold white]. "
            "Se aplicará en el próximo update.",
            title="Preferencia guardada",
            border=SUCCESS,
        )
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
