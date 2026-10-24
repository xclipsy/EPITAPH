"""Persistencia de preferencias (.epitaph/preferences.toml)."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VERSION = 1


@dataclass
class Preference:
    id: str
    origin: str
    created_at: str
    scope: str
    value: Any
    note: str = ""


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        inner = ", ".join(f"{key} = {_toml_value(item)}" for key, item in value.items())
        return "{ " + inner + " }"
    raise TypeError(f"valor no soportado: {type(value)!r}")


def dump(preferences: list[Preference]) -> str:
    lines = [f"version = {VERSION}", ""]
    for preference in preferences:
        lines.append("[[preference]]")
        lines.append(f"id = {_toml_value(preference.id)}")
        lines.append(f"origin = {_toml_value(preference.origin)}")
        lines.append(f"created_at = {_toml_value(preference.created_at)}")
        lines.append(f"scope = {_toml_value(preference.scope)}")
        lines.append(f"value = {_toml_value(preference.value)}")
        if preference.note:
            lines.append(f"note = {_toml_value(preference.note)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load_file(path: Path) -> list[Preference]:
    if not path.exists():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return []
    items: list[Preference] = []
    for raw in data.get("preference", []):
        if not isinstance(raw, dict) or "id" not in raw or "scope" not in raw:
            continue
        items.append(
            Preference(
                id=str(raw["id"]),
                origin=str(raw.get("origin", "file")),
                created_at=str(raw.get("created_at", "")),
                scope=str(raw["scope"]),
                value=raw.get("value"),
                note=str(raw.get("note", "")),
            )
        )
    return items


class PreferenceStore:
    def __init__(self, path: Path, max_items: int = 20) -> None:
        self.path = Path(path)
        self.max_items = max_items
        self.items: list[Preference] = load_file(self.path)

    @classmethod
    def for_root(cls, root: Path, relative: str = ".epitaph/preferences.toml", max_items: int = 20):
        return cls(Path(root) / relative, max_items=max_items)

    @classmethod
    def global_path(cls) -> Path:
        return Path.home() / ".config" / "epitaph" / "preferences.toml"

    # ------------------------------------------------------------------- CRUD

    def add(self, scope: str, value: Any, note: str = "", origin: str = "chat") -> Preference:
        next_number = 1 + max(
            (int(item.id.split("-")[-1]) for item in self.items if item.id.startswith("pref-")),
            default=0,
        )
        preference = Preference(
            id=f"pref-{next_number:03d}",
            origin=origin,
            created_at=_now(),
            scope=scope,
            value=value,
            note=note[:240],
        )
        self.items.append(preference)
        self.items = self.items[-self.max_items :]
        self.save()
        return preference

    def remove(self, preference_id: str) -> bool:
        before = len(self.items)
        self.items = [item for item in self.items if item.id != preference_id]
        if len(self.items) != before:
            self.save()
            return True
        return False

    def clear(self) -> None:
        self.items = []
        self.save()

    def get(self, preference_id: str) -> Preference | None:
        return next((item for item in self.items if item.id == preference_id), None)

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(dump(self.items), encoding="utf-8")
        return self.path
