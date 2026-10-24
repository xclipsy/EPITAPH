"""Matriz de permisos por operación."""

from __future__ import annotations

from ..config import Config
from ..errors import PermissionDenied

ACTIONS = {
    "read": None,
    "write:readme": "write_readme",
    "write:requirements": "write_requirements",
    "write:suggestions": "write_suggestions",
    "write:code": "write_code",
    "network": "network",
}


def check(config: Config, action: str) -> str:
    """Devuelve 'allow', 'ask' o 'deny'."""
    field = ACTIONS.get(action)
    if action == "read":
        return "allow"
    if field is None:
        return "deny"
    raw = getattr(config.permissions, field)
    if isinstance(raw, bool):
        return "allow" if raw else "deny"
    return raw if raw in ("allow", "ask", "deny") else "deny"


def is_allowed(config: Config, action: str) -> bool:
    return check(config, action) == "allow"


def require(config: Config, action: str) -> None:
    verdict = check(config, action)
    if verdict == "deny":
        raise PermissionDenied(
            f"permiso denegado para '{action}'",
            hint="cambia el permiso en .epitaph/config.toml ([permissions]) o con /permissions",
        )
