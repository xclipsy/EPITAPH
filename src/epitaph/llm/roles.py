"""Resolución de modelo por rol con fallback explícito."""

from __future__ import annotations

from ..config import Config
from ..errors import LLMUnavailable


def installed_names(models: list[dict]) -> list[str]:
    names: list[str] = []
    for model in models:
        name = model.get("name") or model.get("model") or ""
        if name:
            names.append(name)
    return names


def resolve_model(role: str, config: Config, installed: list[str]) -> str:
    if not installed:
        raise LLMUnavailable(
            "no hay modelos instalados en Ollama",
            hint="ejecuta `epitaph models pull qwen2.5-coder:3b`",
        )

    preferred = getattr(config.llm.roles, role, config.llm.roles.writer)
    if preferred in installed:
        return preferred

    for candidate in (config.llm.roles.writer, config.llm.roles.summarizer, *installed):
        if candidate in installed:
            return candidate
    return installed[0]
