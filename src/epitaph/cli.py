"""Interfaz de línea de comandos de EPITAPH."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import __version__, pipeline, requirements, safety, suggestions
from .analyzers import analyze
from .config import Config
from .errors import EpitaphError, LLMUnavailable
from .llm.hardware import (
    detect as detect_hardware,
)
from .llm.hardware import (
    estimate_ram_gb,
    estimate_tokens_per_second,
    viable,
)
from .llm.health import probe
from .llm.provider_ollama import OllamaProvider
from .llm.roles import installed_names
from .preferences import PreferenceStore, build, detect, resolve, validate
from .preferences.apply import directives_text
from .scheduler.trigger import Trigger, parse_spec
from .scheduler.watcher import Watcher
from .scheduler.worker import Worker
from .state import State
from .ui import banner
from .ui.components import (
    catalog_table,
    diff_panel,
    info_panel,
    kv_panel,
    tip,
)
from .ui.notices import doctor_table, ollama_notice
from .ui.tables import facts_panel, models_table
from .ui.theme import PRIMARY, SECONDARY, SUCCESS, console, use_rich


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="epitaph",
        description="Documentación viva, local y no destructiva.",
    )
    parser.add_argument("--version", action="version", version=f"epitaph {__version__}")
    parser.add_argument(
        "-C",
        "--path",
        default=None,
        help="ruta del proyecto (default: workspace activo o .)",
    )
    parser.add_argument("--no-llm", action="store_true", help="no usar el modelo")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("chat", help="abre el chat interactivo (default)")
    sub.add_parser("init", help="configuración inicial")

    for name, help_text in (
        ("update", "analiza y actualiza la documentación"),
        ("docs", "regenera el README (alias de update)"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--dry", action="store_true", help="no escribe nada")
        command.add_argument("--yes", action="store_true", help="aprueba escrituras 'ask'")
        command.add_argument("--force", action="store_true", help="ignora el árbol de git sucio")
        command.add_argument("--json", action="store_true", help="salida JSON del análisis")
        command.add_argument(
            "--no-llm",
            action="store_true",
            default=argparse.SUPPRESS,
            help="no usar el modelo (también válido antes del subcomando)",
        )

    analyze_cmd = sub.add_parser("analyze", help="análisis determinista en JSON")
    analyze_cmd.add_argument("--json", action="store_true")

    req = sub.add_parser("requirements", help="analiza dependencias")
    req.add_argument("--audit", action="store_true", help="solo reporta")

    sub.add_parser("suggestions", help="genera el informe de sugerencias")

    prefs = sub.add_parser("prefs", help="gestiona preferencias")
    prefs.add_argument("action", nargs="?", default="list", choices=["list", "add", "rm", "clear"])
    prefs.add_argument("value", nargs="?", default="")
    prefs.add_argument("--yes", action="store_true")

    structure = sub.add_parser("structure", help="estructura del README")
    structure.add_argument("action", nargs="?", default="show", choices=["show", "reset"])

    models = sub.add_parser("models", help="gestiona modelos locales")
    models.add_argument("action", nargs="?", default="list", choices=["list", "use", "pull", "role"])
    models.add_argument("value", nargs="?", default="")
    models.add_argument("role", nargs="?", default="")

    bench = sub.add_parser("bench", help="mide el rendimiento del modelo")
    bench.add_argument("--model", default="")

    sub.add_parser("doctor", help="diagnóstico del entorno")

    undo = sub.add_parser("undo", help="restaura backups")
    undo.add_argument("--list", action="store_true")

    watch = sub.add_parser("watch", help="vigila el proyecto")
    watch.add_argument("--daemon", action="store_true")
    watch.add_argument("--once", action="store_true", help="un solo run y sale")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        root = (
            Path(args.path).expanduser().resolve()
            if args.path is not None
            else Path.cwd().resolve()
        )
    else:
        root = _resolve_root(args.path)

    try:
        if args.command in (None, "chat"):
            config = _require_config(root)
            if (code := _ensure_llm(config, command="epitaph")) is not None:
                return code
            state = State.load(root)
            from .ui.chat import ChatSession

            return ChatSession(root, config, state).run()

        if args.command == "init":
            config = Config.load_or_default(root)
            from .ui.wizard import run as wizard_run

            res = wizard_run(root, config)
            root, config = res.root, res.config
            from .fs import set_active_workspace

            set_active_workspace(root)
            info_panel(
                f"Configuración completada para [bold white]{root}[/bold white].\n"
                f"[{SECONDARY}]cadencia:[/] [bold white]{config.trigger.default}[/bold white]\n"
                f"[{SECONDARY}]siguiente paso:[/] [bold {SUCCESS}]epitaph[/bold {SUCCESS}]",
                title="EPITAPH listo",
                border=SUCCESS,
            )
            return 0

        if args.command == "analyze":
            facts = analyze(root)
            if args.json:
                print(json.dumps(facts, ensure_ascii=False, indent=2))
            else:
                facts_panel(facts)
            return 0

        if args.command in ("update", "docs"):
            config = _require_config(root)
            if (
                code := _ensure_llm(
                    config,
                    command=f"epitaph {args.command}",
                    no_llm=args.no_llm,
                )
            ) is not None:
                return code
            state = State.load(root)
            provider = None if args.no_llm else OllamaProvider(config.llm.base_url)
            result = pipeline.update(
                root,
                config,
                state,
                provider=provider,
                use_llm=not args.no_llm,
                dry_run=args.dry,
                force=args.force,
                auto_approve=args.yes,
            )
            if args.json:
                print(
                    json.dumps(
                        {
                            "changed": bool(result.merge and result.merge.changed),
                            "written": result.written,
                            "changes": result.merge.changes if result.merge else [],
                            "skipped": result.skipped_reason,
                            "tokens_in": result.tokens_in,
                            "tokens_out": result.tokens_out,
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                _render_update(result)
            return 0

        if args.command == "requirements":
            config = _require_config(root)
            facts = analyze(root)
            result = requirements.analyze(root, facts, config)
            diff = requirements.render_diff(root, config, result)
            if diff:
                diff_panel("requirements.txt · propuesta", diff)
            else:
                info_panel(
                    "Las dependencias declaradas coinciden.",
                    title="requirements.txt",
                    border=SUCCESS,
                )
            if not args.audit and result["missing"]:
                target = requirements.write_suggested(root, config, result)
                tip(f"propuesta escrita en {target}")
            return 0

        if args.command == "suggestions":
            config = _require_config(root)
            facts = analyze(root)
            deps = requirements.analyze(root, facts, config)
            items = suggestions.build(facts, deps, root)
            store = PreferenceStore.for_root(root, config.preferences.path)
            effective = resolve(config, store.items)
            path, selected, hidden_prefs, hidden_status = suggestions.write_report(
                root, config, items, effective
            )
            kv_panel(
                "Sugerencias generadas",
                [
                    ("archivo", str(path)),
                    ("incluidas", str(len(selected))),
                    ("ocultas por preferencias", str(hidden_prefs)),
                    ("descartadas antes", str(hidden_status)),
                ],
                border=SUCCESS,
                footer=f"revisa {path.name} antes de aplicarlo",
            )
            return 0

        if args.command == "prefs":
            return _prefs(root, args)

        if args.command == "structure":
            return _structure(root, args)

        if args.command == "models":
            return _models(root, args)

        if args.command == "bench":
            return _bench(root, args)

        if args.command == "doctor":
            return _doctor(root)

        if args.command == "undo":
            return _undo(root, args)

        if args.command == "watch":
            return _watch(root, args)

        parser.print_help()
        return 0

    except EpitaphError as exc:
        print(exc.render(), file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\ninterrumpido", file=sys.stderr)
        return 130


# ------------------------------------------------------------------ helpers


def _resolve_root(path_arg: str | None) -> Path:
    """Resuelve la carpeta de trabajo del proyecto."""
    if path_arg is not None:
        return Path(path_arg).expanduser().resolve()

    from .fs import get_active_workspace

    active = get_active_workspace()
    if active is not None and active.exists() and active.is_dir():
        return active

    cwd = Path.cwd().resolve()
    cfg_file = cwd / ".epitaph" / "config.toml"
    if cfg_file.exists():
        try:
            c = Config.load_or_default(cwd)
            if c.project.target_path:
                tp = Path(c.project.target_path).expanduser().resolve()
                if tp.exists() and tp.is_dir():
                    return tp
        except Exception:
            pass
        return cwd

    return cwd


def _require_config(root: Path) -> Config:
    return Config.load(root)


def _ensure_llm(
    config: Config,
    *,
    command: str,
    no_llm: bool = False,
    require_models: bool = True,
    deterministic: str | None = "epitaph update --no-llm",
) -> int | None:
    """Bloquea comandos que necesitan Ollama si el servicio no está listo."""
    if no_llm:
        return None
    health = probe(OllamaProvider(config.llm.base_url))
    if health.reachable and (health.models or not require_models):
        return None
    ollama_notice(
        health,
        command=command,
        model=config.llm.roles.writer,
        deterministic=deterministic,
    )
    return LLMUnavailable.exit_code


def _print(text: str) -> None:
    if use_rich():
        console().print(text)
    else:
        print(text)


def _render_update(result) -> None:
    changes = result.merge.changes if result.merge else []
    if result.written:
        state = f"[bold {SUCCESS}]README actualizado[/bold {SUCCESS}]"
    elif result.skipped_reason:
        state = f"[{SECONDARY}]{result.skipped_reason}[/]"
    else:
        state = f"[{SECONDARY}]sin cambios[/]"

    body = [
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


def _prefs(root: Path, args) -> int:
    config = _require_config(root)
    store = PreferenceStore.for_root(root, config.preferences.path)

    if args.action == "add" and args.value:
        proposal = build(args.value, detect(args.value).scope_hint, config, len(store.items))
        if proposal is None:
            info_panel(
                "No pude convertir eso en una preferencia concreta.",
                title="Preferencias",
                border=PRIMARY,
            )
            return 1
        ok, error = validate(proposal, config)
        if not ok:
            info_panel(f"No se puede aplicar: {error}", title="Preferencias", border=PRIMARY)
            return 1
        kv_panel(
            "Propuesta de preferencia",
            [
                ("ámbito", proposal.scope),
                ("valor", str(proposal.value)),
                ("motivo", proposal.reason or "—"),
            ],
        )
        if not args.yes:
            tip("añade --yes para guardarla")
            return 0
        preference = store.add(proposal.scope, proposal.value, proposal.reason)
        safety.log(root, "preference:add", id=preference.id, scope=preference.scope)
        info_panel(
            f"Guardada como [bold white]{preference.id}[/bold white].",
            title="Preferencia guardada",
            border=SUCCESS,
        )
        return 0

    if args.action == "rm" and args.value:
        if store.remove(args.value):
            info_panel(
                f"Eliminada [bold white]{args.value}[/bold white].",
                title="Preferencias",
                border=SUCCESS,
            )
            return 0
        info_panel("No existe.", title="Preferencias", border=PRIMARY)
        return 1

    if args.action == "clear":
        if not args.yes:
            tip("añade --yes para borrar todas las preferencias")
            return 0
        store.clear()
        info_panel("Preferencias eliminadas.", title="Preferencias", border=SUCCESS)
        return 0

    if not store.items:
        info_panel("No hay preferencias.", title="Preferencias", border=SECONDARY)
        return 0
    rows = [
        (preference.id, preference.scope, str(preference.value)[:60], preference.origin)
        for preference in store.items
    ]
    catalog_table("Preferencias guardadas", ["ID", "Ámbito", "Valor", "Origen"], rows)
    info_panel(
        directives_text(resolve(config, store.items)),
        title="Directivas activas",
        border=SECONDARY,
    )
    return 0


def _structure(root: Path, args) -> int:
    config = _require_config(root)
    store = PreferenceStore.for_root(root, config.preferences.path)
    if args.action == "reset":
        store.items = [item for item in store.items if item.scope != "readme.structure"]
        store.save()
        config.readme.sections = list(Config.default().readme.sections)
        config.save(root)
        info_panel(
            "Estructura del README restablecida.",
            title="Estructura",
            border=SUCCESS,
        )
        return 0
    effective = resolve(config, store.items)
    rows = [(str(index), section) for index, section in enumerate(effective.sections, 1)]
    catalog_table("Estructura efectiva del README", ["#", "Sección"], rows)
    if effective.sections != config.readme.sections:
        tip("la estructura está modificada por preferencias; usa `epitaph structure reset`")
    return 0


def _models(root: Path, args) -> int:
    config = _require_config(root)
    provider = OllamaProvider(config.llm.base_url)
    hw = detect_hardware()

    if args.action in ("list", "pull"):
        if (
            code := _ensure_llm(
                config,
                command=f"epitaph models {args.action}",
                require_models=False,
                deterministic=None,
            )
        ) is not None:
            return code

    if args.action == "pull":
        if not args.value:
            _print("Uso: epitaph models pull <modelo>")
            return 1
        _print(f"Descargando {args.value}…")
        last = ""
        for event in provider.pull(args.value):
            status = event.get("status", "")
            if status and status != last:
                _print(f"  {status}")
                last = status
        _print("Listo.")
        return 0

    if args.action == "use":
        if not args.value:
            kv_panel(
                "Modelo activo",
                [("writer", config.llm.roles.writer)],
                footer="usa `epitaph models use <modelo>` para fijar uno global",
            )
            return 0
        for role in ("summarizer", "writer", "advisor", "chat"):
            setattr(config.llm.roles, role, args.value)
        config.save(root)
        info_panel(
            f"Todos los roles usan [bold white]{args.value}[/bold white].",
            title="Modelo global",
            border=SUCCESS,
        )
        return 0

    if args.action == "role":
        if not args.value or not args.role:
            info_panel(
                "Uso: `epitaph models role <rol> <modelo>`",
                title="Roles",
                border=PRIMARY,
            )
            tip("roles disponibles: summarizer, writer, advisor, chat")
            return 1
        if not hasattr(config.llm.roles, args.value):
            info_panel("Rol desconocido.", title="Roles", border=PRIMARY)
            tip("roles disponibles: summarizer, writer, advisor, chat")
            return 1
        setattr(config.llm.roles, args.value, args.role)
        config.save(root)
        kv_panel(
            "Rol actualizado",
            [("rol", args.value), ("modelo", args.role)],
            border=SUCCESS,
        )
        return 0

    models = provider.list_models()
    models_table(models, active=config.llm.roles.writer, hardware=hw)
    return 0


def _bench(root: Path, args) -> int:
    config = _require_config(root)
    if (code := _ensure_llm(config, command="epitaph bench", deterministic=None)) is not None:
        return code
    provider = OllamaProvider(config.llm.base_url)
    models = installed_names(provider.list_models())
    model = args.model or config.llm.roles.writer
    if model not in models:
        model = models[0] if models else model
    _print(f"Midiendo {model}…")
    started = time.time()
    try:
        provider.chat(
            model,
            [{"role": "user", "content": "Responde solo: ok"}],
            num_predict=8,
            num_ctx=1024,
        )
    except EpitaphError as exc:
        _print(exc.render())
        return exc.exit_code
    elapsed = time.time() - started
    hw = detect_hardware()
    payload = next((item for item in provider.list_models() if item.get("name") == model), {})
    ok, reason = viable(payload, hw)
    kv_panel(
        "Benchmark local",
        [
            ("modelo", model),
            ("respuesta", f"{elapsed:.2f} s"),
            ("RAM estimada", f"{estimate_ram_gb(payload):.1f} GB"),
            ("tok/s estimados", f"{estimate_tokens_per_second(payload, hw):.0f}"),
            ("viable", f"{'sí' if ok else 'no'} ({reason})"),
        ],
        border=SUCCESS if ok else PRIMARY,
    )
    return 0


def _doctor(root: Path) -> int:
    import platform

    config = Config.load_or_default(root)
    hw = detect_hardware()
    health = probe(OllamaProvider(config.llm.base_url))
    clean, _ = safety.status(root)

    ok = f"[bold {SUCCESS}]OK[/bold {SUCCESS}]"
    bad = f"[bold {PRIMARY}]NO DISPONIBLE[/bold {PRIMARY}]"
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
            f"[bold {SUCCESS}]CONECTADO[/bold {SUCCESS}]" if health.reachable else bad,
            health.base_url,
        ),
        (
            "modelos",
            f"[bold {SUCCESS}]{len(health.models)}[/bold {SUCCESS}]"
            if health.models
            else f"[bold {PRIMARY}]NINGUNO[/bold {PRIMARY}]",
            ", ".join(health.models) or f"ollama pull {config.llm.roles.writer}",
        ),
        (
            "git",
            f"[bold {SUCCESS}]LIMPIO[/bold {SUCCESS}]"
            if clean
            else f"[bold {PRIMARY}]CON CAMBIOS[/bold {PRIMARY}]",
            "árbol de trabajo",
        ),
        ("config", ok, str(Config.path_for(root))),
    ]
    doctor_table(rows)
    return 0


def _undo(root: Path, args) -> int:
    config = Config.load_or_default(root)
    backups = safety.list_backups(root, Path(config.readme.path).name)
    if not backups:
        info_panel("No hay backups.", title="Undo", border=SECONDARY)
        return 1
    if args.list:
        rows = [(str(index), backup.name) for index, backup in enumerate(backups, 1)]
        catalog_table("Backups disponibles", ["#", "Archivo"], rows)
        return 0
    latest = backups[0]
    safety.restore(latest, root / config.readme.path)
    safety.log(root, "undo:readme", backup=str(latest))
    info_panel(
        f"README restaurado desde [bold white]{latest}[/bold white].",
        title="Undo completado",
        border=SUCCESS,
    )
    return 0


def _watch(root: Path, args) -> int:
    config = _require_config(root)
    if (code := _ensure_llm(config, command="epitaph watch")) is not None:
        return code
    state = State.load(root)
    spec = parse_spec(config.trigger_for("readme"))
    trigger = Trigger(
        spec,
        debounce_seconds=config.trigger.safety.debounce_seconds,
        cooldown_seconds=config.trigger.safety.cooldown_seconds,
    )
    pending: set[str] = set()
    clock = {"last_event": None, "last_run": None}

    if not args.daemon:
        banner.show(
            animate=False,
            model=config.llm.roles.writer,
            project=config.project_name(root),
        )
    info_panel(
        f"[{SECONDARY}]vigilando:[/] {root}\n"
        f"[{SECONDARY}]cadencia:[/] {spec.label}\n"
        f"[{SECONDARY}]modo:[/] {'daemon' if args.daemon else 'interactivo'}",
        title="Watcher activo",
        border=SUCCESS,
    )

    def job() -> None:
        try:
            result = pipeline.update(
                root,
                config,
                state,
                provider=OllamaProvider(config.llm.base_url),
                use_llm=True,
                auto_approve=safety.check(config, "write:readme") == "allow",
            )
            _render_update(result)
        except EpitaphError as exc:
            _print(exc.render())
        finally:
            pending.clear()
            clock["last_run"] = time.time()

    worker = Worker(job)
    worker.start()

    def on_change(paths: list[str]) -> None:
        pending.update(paths)
        clock["last_event"] = time.time()
        state.mark_pending(paths)
        state.save(root)

    watcher = Watcher(root, on_change)
    watcher.start()

    try:
        while True:
            if args.once:
                worker.submit()
                while worker.busy:
                    time.sleep(0.2)
                return 0
            if trigger.should_run(
                now=time.time(),
                last_event=clock["last_event"],
                last_run=clock["last_run"],
                pending=bool(pending),
                busy=worker.busy,
                paused=state.paused,
            ):
                worker.submit()
            time.sleep(0.5)
    except KeyboardInterrupt:
        _print("detenido")
        return 0
    finally:
        watcher.stop()
        worker.stop()


if __name__ == "__main__":
    raise SystemExit(main())
