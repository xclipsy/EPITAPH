"""Estado persistente del proyecto (.epitaph/state.json)."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

STATE_VERSION = 1


@dataclass
class State:
    schema_version: int = STATE_VERSION
    last_run: str | None = None
    last_success: str | None = None
    paused: bool = False
    pending: list[str] = field(default_factory=list)
    fingerprints: dict[str, str] = field(default_factory=dict)
    wizard_completed: bool = False

    @staticmethod
    def path_for(root: Path) -> Path:
        return Path(root) / ".epitaph" / "state.json"

    @classmethod
    def load(cls, root: Path) -> State:
        path = cls.path_for(root)
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        known = {key: raw[key] for key in raw if key in cls.__dataclass_fields__}
        return cls(**known)

    def save(self, root: Path) -> Path:
        path = self.path_for(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n")
        return path

    def mark_pending(self, paths: list[str]) -> None:
        merged = list(dict.fromkeys([*self.pending, *paths]))
        self.pending = merged

    def clear_pending(self) -> None:
        self.pending = []


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
