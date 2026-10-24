"""Registro de auditoría append-only."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def log(root: Path, action: str, **fields: Any) -> Path:
    path = Path(root) / ".epitaph" / "audit.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action": action,
        **fields,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return path


def tail(root: Path, limit: int = 20) -> list[dict]:
    path = Path(root) / ".epitaph" / "audit.log"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    events: list[dict] = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
