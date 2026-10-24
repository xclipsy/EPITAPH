from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from epitaph.config import Config
from epitaph.errors import InvalidModelOutput
from epitaph.llm.contract import (
    PreferenceProposal,
    ProsePayload,
    filter_notes,
    parse_proposal,
    parse_prose,
)
from epitaph.llm.prompts import build_messages
from epitaph.preferences import PreferenceStore, resolve


def test_parse_prose_accepts_fenced_json() -> None:
    raw = '```json\n{"overview": "Hola", "confidence": 0.8}\n```'
    payload = parse_prose(raw)
    assert isinstance(payload, ProsePayload)
    assert payload.overview == "Hola"
    assert payload.confidence == 0.8


def test_parse_prose_rejects_plain_text() -> None:
    with pytest.raises(InvalidModelOutput):
        parse_prose("esto no es json")


def test_parse_prose_rejects_broken_json() -> None:
    with pytest.raises(InvalidModelOutput):
        parse_prose('{"overview": "Hola", }')


def test_prose_fields_are_capped() -> None:
    payload = parse_prose(json.dumps({"overview": "x" * 2000}))
    assert len(payload.overview) == 700


def test_filter_notes_drops_unknown_paths() -> None:
    payload = parse_prose(
        json.dumps(
            {
                "module_notes": [
                    {"path": "app/core.py", "purpose": "núcleo"},
                    {"path": "inventado.py", "purpose": "no existe"},
                ]
            }
        )
    )
    facts = {"modules": [{"path": "app/core.py"}]}
    filtered = filter_notes(payload, facts)
    assert [note.path for note in filtered.module_notes] == ["app/core.py"]


def test_proposal_rejects_unknown_scope() -> None:
    with pytest.raises(ValidationError):
        parse_proposal(
            json.dumps(
                {
                    "intent": "preference",
                    "scope": "permissions.write_readme",
                    "value": "allow",
                }
            )
        )


def test_proposal_rejects_unknown_action() -> None:
    with pytest.raises(ValidationError):
        PreferenceProposal(scope="readme.style", action="delete", value={"tone": "informal"})


def test_prompts_mask_secrets_in_docstrings(tmp_path) -> None:
    facts = {
        "name": "demo",
        "languages": [],
        "totals": {},
        "entrypoints": [],
        "commands": {},
        "cycles": [],
        "orphans": [],
        "modules": [
            {
                "path": "app/config.py",
                "lang": "python",
                "loc": 3,
                "docstring": "config api_key = 'supersecreto123'",
                "functions": [],
            }
        ],
    }
    config = Config.default("demo")
    effective = resolve(config, [])
    messages = build_messages(facts, effective)

    joined = "\n".join(message["content"] for message in messages)
    assert "supersecreto123" not in joined
    assert "REDACTED" in joined


def test_prompts_include_confirmed_directives(tmp_path) -> None:
    store = PreferenceStore(tmp_path / "prefs.toml")
    store.add("prompt.directives", "No incluir ejemplos de Docker.")
    store.add("readme.style", {"tone": "informal"})

    config = Config.default("demo")
    effective = resolve(config, store.items)
    messages = build_messages({"name": "demo"}, effective)

    system = messages[0]["content"]
    assert "No incluir ejemplos de Docker." in system
    assert "informal" in system
