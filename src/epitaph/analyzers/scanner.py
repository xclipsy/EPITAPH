"""Recorrido del repositorio con respeto a .gitignore y denylist."""

from __future__ import annotations

import fnmatch
from collections.abc import Iterator
from pathlib import Path

try:  # pragma: no cover - dependencia opcional en tests aislados
    import pathspec
except ImportError:  # pragma: no cover
    pathspec = None

DENY_DIRS = {
    ".git",
    ".epitaph",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "target",
    ".idea",
    ".vscode",
    ".tox",
    ".nox",
    "vendor",
    "coverage",
    "htmlcov",
}

DENY_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".bin",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".7z",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".mp4",
    ".mp3",
    ".lock",
    ".db",
    ".sqlite",
    ".sqlite3",
}

# Artefactos que EPITAPH genera dentro del repositorio. Excluirlos evita que
# su propia salida altere el árbol y rompa la idempotencia.
DENY_FILES = {
    "suggestions.md",
    "requirements.suggested.txt",
    "README.suggested.md",
}

MAX_FILE_BYTES = 2_000_000
MAX_FILES = 20_000


class Scanner:
    def __init__(
        self,
        root: Path,
        extra_ignore: list[str] | None = None,
        max_files: int = MAX_FILES,
        max_bytes: int = MAX_FILE_BYTES,
    ) -> None:
        self.root = Path(root).resolve()
        self.max_files = max_files
        self.max_bytes = max_bytes
        self._ignore_spec = self._load_spec(self.root / ".gitignore")
        self._extra = extra_ignore or []
        self._extra_spec = self._load_spec(self.root / ".epitaphignore", extra=self._extra)
        self.truncated = False

    # ------------------------------------------------------------- internals

    def _load_spec(self, path: Path, extra: list[str] | None = None):
        patterns: list[str] = []
        if path.exists():
            try:
                patterns.extend(
                    line.strip()
                    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                )
            except OSError:
                pass
        if extra:
            patterns.extend(extra)
        if pathspec is not None:
            return pathspec.GitIgnoreSpec.from_lines(patterns)
        return patterns

    def _match(self, spec, rel: str, is_dir: bool) -> bool:
        candidate = rel + ("/" if is_dir else "")
        if pathspec is not None and spec is not None:
            return bool(spec.match_file(candidate))
        if isinstance(spec, list):
            return any(
                fnmatch.fnmatch(candidate, pattern) or fnmatch.fnmatch(rel, pattern)
                for pattern in spec
            )
        return False

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    # ------------------------------------------------------------------- API

    def is_ignored(self, path: Path, is_dir: bool | None = None) -> bool:
        try:
            rel = self.rel(path)
        except ValueError:
            return True
        if rel == ".":
            return False
        if is_dir is None:
            is_dir = path.is_dir()

        parts = set(Path(rel).parts)
        if parts & DENY_DIRS:
            return True
        if not is_dir and Path(rel).name in DENY_FILES:
            return True
        if not is_dir and path.suffix.lower() in DENY_EXTENSIONS:
            return True
        if self._match(self._ignore_spec, rel, is_dir):
            return True
        if self._match(self._extra_spec, rel, is_dir):
            return True
        return False

    def iter_files(self) -> Iterator[Path]:
        count = 0
        for path in sorted(self.root.rglob("*")):
            if path.is_dir() or path.is_symlink():
                continue
            if self.is_ignored(path, is_dir=False):
                continue
            try:
                if path.stat().st_size > self.max_bytes:
                    continue
            except OSError:
                continue
            count += 1
            if count > self.max_files:
                self.truncated = True
                break
            yield path

    def iter_dirs(self) -> Iterator[Path]:
        for path in sorted(self.root.rglob("*")):
            if path.is_dir() and not self.is_ignored(path, is_dir=True):
                yield path
