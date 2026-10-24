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
from .errors import EpitaphError
from .llm.hardware import (
    detect as detect_hardware,
)
from .llm.hardware import (
    estimate_ram_gb,
    estimate_tokens_per_second,
    viable,
)
from .llm.provider_ollama import OllamaProvider
from .llm.roles import installed_names
from .preferences import PreferenceStore, build, detect, resolve, validate
from .preferences.apply import directives_text
from .scheduler.trigger import Trigger, parse_spec
from .scheduler.watcher import Watcher
from .scheduler.worker import Worker
from .state import State
from .ui import banner
from .ui.tables import facts_panel, models_table
from .ui.theme import SECONDARY, SUCCESS, console, use_rich, write


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="epitaph",
        description="Documentación viva, local y no destructiva.",
    )
    parser.add_argument("--version", action="version", version=f"epitaph {__version__}")
    parser.add_argument("-C", "--path", default=".", help="ruta del proyecto (default: .)")
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

    describe_cmd = sub.add_parser(
        "describe", help="lee una carpeta y describe el proyecto (no escribe nada)"
    )
    describe_cmd.add_argument("path", nargs="?", default="", help="carpeta a describir")
    describe_cmd.add_argument("--json", action="store_true", help="salida JSON completa")
    describe_cmd.add_argument(
        "--md",
        "--markdown",
        dest="markdown",
        action="store_true",
        help="README completo en Markdown",
    )
    describe_cmd.add_argument("--out", default="", help="guarda el Markdown en un archivo")
    describe_cmd.add_argument("--model", default="", help="modelo local para la prosa")
    describe_cmd.add_argument(
        "--no-llm",
        action="store_true",
        default=argparse.SUPPRESS,
        help="solo análisis determinista (también válido antes del subcomando)",
    )

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
    root = Path(args.path).expanduser().resolve()

    try:
        if args.command in (None, "chat"):
            config = _require_config(root)
            state = State.load(root)
            from .ui.chat import ChatSession

            return ChatSession(root, config, state).run()

        if args.command == "init":
            config = Config.load_or_default(root)
            from .ui.wizard import run as wizard_run

            wizard_run(root, config)
            state = State.load(root)
            state.wizard_completed = True
            state.save(root)
            _print("Listo. Ejecuta `epitaph` para abrir el chat.")
            return 0

        if args.command == "analyze":
            facts = analyze(root)
            if args.json:
                print(json.dumps(facts, ensure_ascii=False, indent=2))
            else:
                facts_panel(facts)
            return 0

        if args.command == "describe":
            return _describe(root, args)

        if args.command in ("update", "docs"):
            config = _require_config(root)
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
            _print(diff or "Sin diferencias: las dependencias declaradas coinciden.")
            if not args.audit and result["missing"]:
                target = requirements.write_suggested(root, config, result)
                _print(f"Propuesta escrita en {target}")
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
            _print(f"{len(selected)} sugerencias en {path}")
            if hidden_prefs or hidden_status:
                _print(f"ocultas: {hidden_prefs} por preferencias, {hidden_status} descartadas")
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


def _describe(root: Path, args) -> int:
    from .describe import describe, render

    target = Path(args.path).expanduser().resolve() if args.path else root
    if not target.is_dir():
        _print(f"No es una carpeta válida: {target}")
        return 2

    config = Config.load_or_default(target)
    if args.model:
        config.llm.roles.chat = args.model

    provider: OllamaProvider | None = None
    if not args.no_llm:
        candidate = OllamaProvider(config.llm.base_url)
        if candidate.is_available():
            provider = candidate
        else:
            candidate.close()

    try:
        description = describe(
            target,
            config=config,
            provider=provider,
            use_llm=provider is not None,
        )
    finally:
        if provider is not None:
            provider.close()

    if args.out:
        output = Path(args.out).expanduser()
        output.write_text(description.markdown, encoding="utf-8")
        _print(f"Markdown escrito en {output}")

    if args.json:
        write(json.dumps(description.to_dict(), ensure_ascii=False, indent=2) + "\n")
    elif args.markdown:
        write(description.markdown.rstrip() + "\n")
    else:
        render(description)
    return 0


def _require_config(root: Path) -> Config:
    return Config.load(root)


def _print(text: str) -> None:
    if use_rich():
        console().print(text)
    else:
        print(text)


def _render_update(result) -> None:
    if result.merge and result.merge.changes:
        for change in result.merge.changes:
            _print(f"  · {change}")
    if result.skipped_reason:
        _print(f"[{SECONDARY}]{result.skipped_reason}[/]")
    if result.written:
        _print(f"[{SUCCESS}]✔ README actualizado[/] ({result.duration_ms} ms)")
    if result.merge and result.merge.errors:
        for error in result.merge.errors:
            _print(f"marcador: {error}")


def _prefs(root: Path, args) -> int:
    config = _require_config(root)
    store = PreferenceStore.for_root(root, config.preferences.path)

    if args.action == "add" and args.value:
        proposal = build(args.value, detect(args.value).scope_hint, config, len(store.items))
        if proposal is None:
            _print("No pude convertir eso en una preferencia concreta.")
            return 1
        ok, error = validate(proposal, config)
        if not ok:
            _print(f"No se puede aplicar: {error}")
            return 1
        _print(f"propuesta: {proposal.scope} = {proposal.value}")
        if not args.yes:
            _print("Añade --yes para guardarla.")
            return 0
        preference = store.add(proposal.scope, proposal.value, proposal.reason)
        safety.log(root, "preference:add", id=preference.id, scope=preference.scope)
        _print(f"Guardada como {preference.id}.")
        return 0

    if args.action == "rm" and args.value:
        if store.remove(args.value):
            _print(f"Eliminada {args.value}.")
            return 0
        _print("No existe.")
        return 1

    if args.action == "clear":
        if not args.yes:
            _print("Añade --yes para borrar todas las preferencias.")
            return 0
        store.clear()
        _print("Preferencias eliminadas.")
        return 0

    if not store.items:
        _print("No hay preferencias.")
        return 0
    for preference in store.items:
        _print(f"{preference.id}  {preference.scope} = {preference.value}  [{preference.origin}]")
    _print("")
    _print(directives_text(resolve(config, store.items)))
    return 0


def _structure(root: Path, args) -> int:
    config = _require_config(root)
    store = PreferenceStore.for_root(root, config.preferences.path)
    if args.action == "reset":
        store.items = [item for item in store.items if item.scope != "readme.structure"]
        store.save()
        config.readme.sections = list(Config.default().readme.sections)
        config.save(root)
        _print("Estructura restablecida.")
        return 0
    effective = resolve(config, store.items)
    for index, section in enumerate(effective.sections, start=1):
        _print(f"{index}. {section}")
    return 0


def _models(root: Path, args) -> int:
    config = _require_config(root)
    provider = OllamaProvider(config.llm.base_url)
    hw = detect_hardware()

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
            _print(f"Modelo actual: {config.llm.roles.writer}")
            return 0
        for role in ("summarizer", "writer", "advisor", "chat"):
            setattr(config.llm.roles, role, args.value)
        config.save(root)
        _print(f"Modelo global: {args.value}")
        return 0

    if args.action == "role":
        if not args.value or not args.role:
            _print("Uso: epitaph models role <rol> <modelo>")
            return 1
        if not hasattr(config.llm.roles, args.value):
            _print("Roles: summarizer, writer, advisor, chat")
            return 1
        setattr(config.llm.roles, args.value, args.role)
        config.save(root)
        _print(f"{args.value} = {args.role}")
        return 0

    models = provider.list_models()
    models_table(models, active=config.llm.roles.writer, hardware=hw)
    return 0


def _bench(root: Path, args) -> int:
    config = _require_config(root)
    provider = OllamaProvider(config.llm.base_url)
    if not provider.is_available():
        _print("Ollama no está disponible.")
        return 3
    models = installed_names(provider.list_models())
    model = args.model or config.llm.roles.writer
    if model not in models:
        model = models[0] if models else model
    _print(f"Midiendo {model}…")
    started = time.time()
    first: dict[str, float | None] = {"at": None}

    def _mark(_token: str) -> None:
        if first["at"] is None:
            first["at"] = time.time() - started

    try:
        provider.chat(
            model,
            [{"role": "user", "content": "Responde solo: ok"}],
            num_predict=8,
            num_ctx=1024,
            on_token=_mark,
        )
    except EpitaphError as exc:
        _print(exc.render())
        return exc.exit_code
    elapsed = time.time() - started
    hw = detect_hardware()
    payload = next((item for item in provider.list_models() if item.get("name") == model), {})
    if first["at"] is not None:
        _print(f"primer token: {first['at']:.2f} s")
    _print(f"tiempo de respuesta: {elapsed:.2f} s")
    _print(f"RAM estimada del modelo: {estimate_ram_gb(payload):.1f} GB")
    _print(f"tok/s estimados: {estimate_tokens_per_second(payload, hw):.0f}")
    ok, reason = viable(payload, hw)
    _print(f"viabilidad: {'sí' if ok else 'no'} ({reason})")
    return 0


def _doctor(root: Path) -> int:
    import platform

    config = Config.load_or_default(root)
    hw = detect_hardware()
    provider = OllamaProvider(config.llm.base_url)
    _print(f"epitaph       {__version__}")
    _print(f"python        {platform.python_version()}")
    _print(f"sistema       {hw.system} {hw.machine} · {hw.cpu_count} hilos")
    _print(f"memoria       {hw.ram_total_gb:.1f} GB ({hw.ram_available_gb:.1f} libres)")
    _print(f"gpu           {hw.gpu or 'no detectada'}")
    _print(f"ollama        {'conectado' if provider.is_available() else 'no disponible'}")
    if provider.is_available():
        try:
            _print(f"modelos       {', '.join(installed_names(provider.list_models())) or 'ninguno'}")
        except EpitaphError:
            pass
    clean, _ = safety.status(root)
    _print(f"git           {'limpio' if clean else 'con cambios'}")
    _print(f"config        {Config.path_for(root)}")
    return 0


def _undo(root: Path, args) -> int:
    config = Config.load_or_default(root)
    backups = safety.list_backups(root, Path(config.readme.path).name)
    if not backups:
        _print("No hay backups.")
        return 1
    if args.list:
        for backup in backups:
            _print(str(backup))
        return 0
    latest = backups[0]
    safety.restore(latest, root / config.readme.path)
    safety.log(root, "undo:readme", backup=str(latest))
    _print(f"Restaurado desde {latest}")
    return 0


def _watch(root: Path, args) -> int:
    config = _require_config(root)
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
        banner.show(animate=False)
    _print(f"vigilando {root} · {spec.label}")

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
