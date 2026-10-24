from __future__ import annotations

from pathlib import Path

from epitaph.config import Config
from epitaph.preferences import (
    PreferenceStore,
    apply_to_config,
    build,
    conflicts,
    detect,
    resolve,
    validate,
)
from epitaph.preferences.apply import filter_suggestions


def test_detect_preference_in_spanish() -> None:
    detection = detect("prefiero el árbol al final y sin badges")
    assert detection.is_preference is True
    assert detection.scope_hint == "readme.structure"


def test_detect_tone_is_style() -> None:
    detection = detect("prefiero que el README sea informal")
    assert detection.is_preference is True
    assert detection.scope_hint == "readme.style"


def test_detect_question_is_not_a_preference() -> None:
    detection = detect("¿por qué hay un ciclo entre core y util?")
    assert detection.is_preference is False


def test_detect_ignores_commands() -> None:
    assert detect("/update --dry").is_preference is False


def test_build_moves_tree_to_the_end() -> None:
    config = Config.default("demo")
    proposal = build("prefiero el árbol al final", "readme.structure", config)
    assert proposal is not None
    assert proposal.scope == "readme.structure"
    assert proposal.value[-1] == "structure"
    assert proposal.requires_confirmation is True


def test_build_disables_badges() -> None:
    config = Config.default("demo")
    proposal = build("no quiero badges en el readme", "readme.structure", config)
    assert proposal is not None
    assert proposal.scope == "readme.style"
    assert proposal.value == {"include_badges": False}


def test_build_modularity_style() -> None:
    config = Config.default("demo")
    detection = detect("sugiere modularización por dominio, no por capas")
    assert detection.scope_hint == "suggestions.modularity"
    proposal = build("sugiere modularización por dominio", detection.scope_hint, config)
    assert proposal is not None
    assert proposal.value == "by-domain"


def test_build_forbidden_framework_change() -> None:
    config = Config.default("demo")
    proposal = build(
        "no quiero que sugieras cambiar de framework", "suggestions.filter", config
    )
    assert proposal is not None
    assert proposal.value == {"forbidden": ["framework-change"]}


def test_validate_rejects_unknown_scope() -> None:
    config = Config.default("demo")
    proposal = build("prefiero el árbol al final", "readme.structure", config)
    assert proposal is not None
    proposal.scope = "permissions.write_readme"
    ok, error = validate(proposal, config)
    assert ok is False
    assert "ámbito" in error


def test_validate_rejects_unknown_sections() -> None:
    config = Config.default("demo")
    proposal = build("prefiero el árbol al final", "readme.structure", config)
    assert proposal is not None
    proposal.value = ["overview", "hackear"]
    ok, _ = validate(proposal, config)
    assert ok is False


def test_preferences_cannot_change_permissions() -> None:
    config = Config.default("demo")
    proposal = build("escribe requirements.txt sin preguntar", None, config)
    assert proposal is not None
    ok, error = validate(proposal, config)
    assert ok is False
    assert "permisos" in error


def test_directives_reject_urls_and_code() -> None:
    config = Config.default("demo")
    proposal = build("usa https://ejemplo.com como guía", None, config)
    assert proposal is not None
    ok, _ = validate(proposal, config)
    assert ok is False


def test_store_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / ".epitaph" / "preferences.toml"
    store = PreferenceStore(path)
    first = store.add("suggestions.modularity", "by-domain", note="por dominio")
    second = store.add("readme.style", {"tone": "informal"}, origin="cli")

    assert first.id == "pref-001"
    assert second.id == "pref-002"
    assert path.exists()

    reloaded = PreferenceStore(path)
    assert [item.id for item in reloaded.items] == ["pref-001", "pref-002"]
    assert reloaded.get("pref-002").value == {"tone": "informal"}
    assert reloaded.remove("pref-001") is True
    assert reloaded.remove("pref-999") is False
    assert len(PreferenceStore(path).items) == 1


def test_store_respects_max_items(tmp_path: Path) -> None:
    store = PreferenceStore(tmp_path / "prefs.toml", max_items=2)
    for index in range(3):
        store.add("prompt.directives", f"regla {index}")
    assert len(store.items) == 2
    assert store.items[-1].value == "regla 2"


def test_resolve_applies_structure_and_style(tmp_path: Path) -> None:
    config = Config.default("demo")
    store = PreferenceStore(tmp_path / "prefs.toml")
    store.add("readme.structure", ["overview", "install", "structure"])
    store.add("readme.style", {"tone": "informal", "include_badges": True})
    store.add("suggestions.modularity", "by-domain")

    effective = resolve(config, store.items)
    assert effective.sections == ["overview", "install", "structure"]
    assert effective.tone == "informal"
    assert effective.include_badges is True
    assert effective.modularity == "by-domain"

    updated = apply_to_config(config, effective)
    assert updated.readme.sections == effective.sections
    assert updated.readme.tone == "informal"


def test_explicit_config_wins_over_preference(tmp_path: Path) -> None:
    config = Config.default("demo")
    config.project.output_language = "en"
    store = PreferenceStore(tmp_path / "prefs.toml")
    store.add("readme.language", "es")
    effective = resolve(config, store.items)
    assert effective.language == "en"


def test_filter_suggestions_never_hides_security(tmp_path: Path) -> None:
    config = Config.default("demo")
    store = PreferenceStore(tmp_path / "prefs.toml")
    store.add("suggestions.filter", {"muted": ["security", "tooling"], "severity": "high"})
    effective = resolve(config, store.items)

    items = [
        {"category": "security", "rule": "secret-detected", "severity": "critical"},
        {"category": "tooling", "rule": "no-tests", "severity": "high"},
        {"category": "modularity", "rule": "large-module", "severity": "low"},
        {"category": "architecture", "rule": "dependency-cycle", "severity": "high"},
    ]
    kept, hidden = filter_suggestions(items, effective)
    rules = {item["rule"] for item in kept}
    assert "secret-detected" in rules
    assert "tooling" not in {item["category"] for item in kept}
    assert "large-module" not in rules
    assert "dependency-cycle" in rules
    assert hidden == 2


def test_conflicts_are_reported(tmp_path: Path) -> None:
    config = Config.default("demo")
    store = PreferenceStore(tmp_path / "prefs.toml")
    store.add("suggestions.modularity", "by-layer")
    proposal = build("sugiere modularización por dominio", "suggestions.modularity", config)
    assert proposal is not None
    notes = conflicts(proposal, store.items)
    assert notes and "by-layer" in notes[0]
