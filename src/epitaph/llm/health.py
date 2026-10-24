"""Preflight del servicio local de Ollama."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..errors import LLMUnavailable
from .provider_ollama import OllamaProvider
from .roles import installed_names


@dataclass(frozen=True)
class OllamaHealth:
    """Estado del servicio local y de los modelos disponibles."""

    reachable: bool
    base_url: str
    models: tuple[str, ...] = field(default_factory=tuple)
    error: str = ""

    @property
    def ready(self) -> bool:
        return self.reachable and bool(self.models)

    @property
    def state(self) -> str:
        if not self.reachable:
            return "servidor no detectado"
        if not self.models:
            return "servidor activo · sin modelos"
        return f"servidor activo · {len(self.models)} modelo(s)"


def probe(provider: OllamaProvider) -> OllamaHealth:
    """Comprueba el endpoint y los modelos sin lanzar excepciones."""
    if not provider.is_available():
        return OllamaHealth(
            reachable=False,
            base_url=provider.base_url,
            error="no se pudo conectar con /api/tags",
        )
    try:
        models = tuple(installed_names(provider.list_models()))
    except LLMUnavailable as exc:
        return OllamaHealth(
            reachable=False,
            base_url=provider.base_url,
            error=exc.message,
        )
    return OllamaHealth(reachable=True, base_url=provider.base_url, models=models)
