"""Informe de sugerencias con ciclo de vida y filtros de preferencias."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import Config
from ..preferences.apply import Effective, filter_suggestions
from .rules import score

STATUS_FILE = ".epitaph/suggestions.json"
VALID_STATUS = {"open", "accepted", "dismissed", "wontfix"}


def load_status(root: Path) -> dict:
    path = Path(root) / STATUS_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_status(root: Path, statuses: dict) -> Path:
    path = Path(root) / STATUS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(statuses, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def set_status(root: Path, key: str, status: str) -> bool:
    if status not in VALID_STATUS:
        return False
    statuses = load_status(root)
    statuses.setdefault(key, {})["status"] = status
    save_status(root, statuses)
    return True


def select(
    items: list[dict],
    effective: Effective,
    statuses: dict,
    max_items: int,
) -> tuple[list[dict], int, int]:
    """Devuelve (seleccionadas, ocultas_por_preferencias, ocultas_por_estado)."""
    visible: list[dict] = []
    hidden_by_status = 0
    for item in items:
        state = statuses.get(item["key"], {})
        if state.get("status") in ("dismissed", "wontfix"):
            if state.get("evidence") == item["evidence_hash"]:
                hidden_by_status += 1
                continue
        visible.append(item)

    visible.sort(key=score, reverse=True)
    filtered, hidden_by_prefs = filter_suggestions(visible, effective)
    return filtered[:max_items], hidden_by_prefs, hidden_by_status


def render(items: list[dict], hidden_prefs: int, hidden_status: int) -> str:
    lines = ["# Sugerencias de EPITAPH", ""]
    if not items:
        lines.append("Sin sugerencias nuevas.")
    for item in items:
        lines.append(f"### [{item['key']}] {item['title']}")
        lines.append(f"- **Categoría**: `{item['category']}` · **Severidad**: `{item['severity']}`")
        lines.append(f"- **Evidencia**: `{item['evidence']}`")
        lines.append(f"- **Acción sugerida**: {item['action']}")
        lines.append(f"- **Estado**: abierta · **Regla**: `{item['rule']}`")
        lines.append("")
    if hidden_prefs:
        lines.append(f"— {hidden_prefs} sugerencias ocultas por preferencias —")
    if hidden_status:
        lines.append(f"— {hidden_status} sugerencias descartadas previamente —")
    return "\n".join(lines).rstrip() + "\n"


def write_report(
    root: Path,
    config: Config,
    items: list[dict],
    effective: Effective,
) -> tuple[Path, list[dict], int, int]:
    statuses = load_status(root)
    selected, hidden_prefs, hidden_status = select(
        items, effective, statuses, config.suggestions.max_items
    )
    for item in items:
        entry = statuses.setdefault(item["key"], {})
        entry.setdefault("status", "open")
        entry["evidence"] = item["evidence_hash"]
        entry["title"] = item["title"]
        entry["category"] = item["category"]
    save_status(root, statuses)

    path = Path(root) / config.suggestions.path
    path.write_text(render(selected, hidden_prefs, hidden_status), encoding="utf-8")
    return path, selected, hidden_prefs, hidden_status
