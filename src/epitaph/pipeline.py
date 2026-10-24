"""Pipeline de actualización: análisis -> prosa -> merge -> escritura segura."""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import requirements, safety, suggestions
from .analyzers import analyze
from .config import Config
from .errors import DirtyWorkTree, EpitaphError, InvalidModelOutput, PermissionDenied
from .fs import atomic_write
from .llm.cache import Cache
from .llm.contract import ProsePayload, filter_notes, parse_prose
from .llm.prompts import build_messages
from .llm.provider_ollama import OllamaProvider
from .llm.roles import installed_names, resolve_model
from .preferences import PreferenceStore
from .preferences.apply import Effective, apply_to_config, resolve
from .readme.merge import MergeResult, merge
from .readme.render import build_sections
from .state import State


@dataclass
class RunResult:
    facts: dict
    effective: Effective
    sections: OrderedDict[str, str]
    merge: MergeResult | None = None
    prose: ProsePayload | None = None
    written: bool = False
    skipped_reason: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    requirements: dict = field(default_factory=dict)
    suggestion_items: list[dict] = field(default_factory=list)
    suggestion_hidden: int = 0
    readme_path: Path | None = None


def update(
    root: Path,
    config: Config,
    state: State,
    *,
    provider: OllamaProvider | None = None,
    use_llm: bool = True,
    dry_run: bool = False,
    force: bool = False,
    auto_approve: bool = False,
) -> RunResult:
    root = Path(root).resolve()
    started = time.time()
    facts = analyze(root)

    deps = requirements.analyze(root, facts, config)
    store = PreferenceStore.for_root(
        root,
        config.preferences.path,
        max_items=config.preferences.max_directives,
    )
    effective = resolve(config, store.items)
    effective_config = apply_to_config(config, effective)

    prose: ProsePayload | None = None
    tokens_in = tokens_out = 0
    if use_llm and config.features.readme:
        prose, tokens_in, tokens_out = _generate_prose(
            root, facts, effective_config, effective, provider
        )

    readme_enabled = config.features.readme
    sections = (
        build_sections(facts, prose, effective_config, root) if readme_enabled else OrderedDict()
    )

    readme_path = root / effective_config.readme.path
    existing = None
    if readme_enabled and readme_path.exists():
        existing = readme_path.read_text(encoding="utf-8")
    result = (
        merge(existing, sections, title=facts.get("name", root.name))
        if readme_enabled
        else None
    )

    if result is not None and result.errors:
        result.suggested = result.suggested or merge(
            None, sections, title=facts.get("name", root.name)
        ).text
        suggested_path = root / "README.suggested.md"
        if not dry_run:
            atomic_write(suggested_path, result.suggested)
        return RunResult(
            facts=facts,
            effective=effective,
            sections=sections,
            merge=result,
            prose=prose,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            skipped_reason="marcadores inválidos: se generó README.suggested.md",
            duration_ms=int((time.time() - started) * 1000),
            requirements=deps,
        )

    run = RunResult(
        facts=facts,
        effective=effective,
        sections=sections,
        merge=result,
        prose=prose,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        requirements=deps,
        readme_path=readme_path,
        duration_ms=int((time.time() - started) * 1000),
    )

    if dry_run:
        run.skipped_reason = "dry-run"
        return run

    if not readme_enabled:
        run.skipped_reason = "readme desactivado"
    elif not result.changed:
        run.skipped_reason = "sin cambios"
    else:
        _guard_write(config, root, force, auto_approve)
        backup = safety.backup_file(readme_path, root, config.safety.backup_retention)
        atomic_write(readme_path, result.text)
        run.written = True
        safety.log(
            root,
            "write:readme",
            file=effective_config.readme.path,
            backup=str(backup) if backup else None,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            changes=result.changes,
            model=effective_config.llm.roles.writer,
        )

    _write_side_artifacts(root, config, effective_config, facts, deps, effective, run)
    _touch_state(root, state, ok=True)
    _record_cache(root, run, result)
    return run


def _write_side_artifacts(
    root: Path,
    config: Config,
    effective_config: Config,
    facts: dict,
    deps: dict,
    effective: Effective,
    run: RunResult,
) -> None:
    if config.features.suggestions:
        items = suggestions.build(facts, deps, root)
        _, selected, hidden_prefs, hidden_status = suggestions.write_report(
            root, effective_config, items, effective
        )
        run.suggestion_items = selected
        run.suggestion_hidden = hidden_prefs + hidden_status

    if config.features.requirements and deps.get("missing"):
        requirements.write_suggested(root, effective_config, deps)


def _record_cache(root: Path, run: RunResult, result: MergeResult | None) -> None:
    try:
        with Cache(root) as cache:
            cache.record_run(
                {
                    "id": f"r-{int(time.time() * 1000)}",
                    "started_at": datetime.now(UTC).isoformat(),
                    "finished_at": datetime.now(UTC).isoformat(),
                    "reason": "manual",
                    "files_changed": len(result.changes) if result else 0,
                    "tokens_in": run.tokens_in,
                    "tokens_out": run.tokens_out,
                    "duration_ms": run.duration_ms,
                    "status": "ok",
                }
            )
    except Exception:
        pass


def _guard_write(config: Config, root: Path, force: bool, auto_approve: bool) -> None:
    verdict = safety.check(config, "write:readme")
    if verdict == "deny":
        raise PermissionDenied(
            "permiso denegado para escribir el README",
            hint="usa /permissions o cambia [permissions].write_readme en la configuración",
        )
    if verdict == "ask" and not auto_approve:
        raise PermissionDenied(
            "el permiso de escritura del README está en 'ask'",
            hint="ejecuta con --yes o cambia el permiso a 'allow'",
        )

    if config.safety.require_clean_git and not force:
        clean, status_text = safety.status(root)
        if not clean:
            raise DirtyWorkTree(
                "el árbol de git tiene cambios sin confirmar",
                hint="haz commit/stash o usa --force para escribir igualmente",
            )


def _touch_state(root: Path, state: State, ok: bool) -> None:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    state.last_run = now
    if ok:
        state.last_success = now
    state.clear_pending()
    state.save(root)


def _generate_prose(
    root: Path,
    facts: dict,
    config: Config,
    effective: Effective,
    provider: OllamaProvider | None,
) -> tuple[ProsePayload | None, int, int]:
    if provider is None:
        return None, 0, 0
    try:
        if not provider.is_available():
            return None, 0, 0
        models = installed_names(provider.list_models())
        model = resolve_model("writer", config, models)
    except EpitaphError:
        return None, 0, 0

    messages = build_messages(facts, effective)
    try:
        raw = provider.chat(
            model,
            messages,
            num_ctx=config.llm.params.num_ctx,
            num_predict=config.llm.params.num_predict,
            temperature=config.llm.params.temperature,
            num_thread=config.llm.params.num_thread,
            keep_alive=config.llm.params.keep_alive,
        )
        payload = filter_notes(parse_prose(raw), facts)
        return payload, 0, 0
    except (EpitaphError, InvalidModelOutput, ValueError):
        return None, 0, 0
    except Exception:
        return None, 0, 0
