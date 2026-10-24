"""Detección de lenguajes y estadísticas agregadas."""

from __future__ import annotations

from pathlib import Path

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".sh": "shell",
    ".sql": "sql",
    ".md": "markdown",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".html": "html",
    ".css": "css",
}

CODE_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
    "go",
    "rust",
    "java",
    "kotlin",
    "ruby",
    "php",
    "c",
    "cpp",
    "csharp",
    "shell",
}


def language_of(path: Path | str) -> str | None:
    return EXTENSION_TO_LANGUAGE.get(Path(path).suffix.lower())


def is_code(path: Path | str) -> bool:
    return language_of(path) in CODE_LANGUAGES


def summarize(modules: list) -> list[dict]:
    """Agrupa módulos por lenguaje con conteos y LOC."""
    stats: dict[str, dict] = {}
    for module in modules:
        entry = stats.setdefault(module.lang, {"name": module.lang, "files": 0, "loc": 0})
        entry["files"] += 1
        entry["loc"] += module.loc
    return sorted(stats.values(), key=lambda item: (-item["loc"], item["name"]))
