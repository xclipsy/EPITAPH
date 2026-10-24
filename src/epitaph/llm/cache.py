"""Caché local de resúmenes y fingerprints (SQLite, WAL)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS summaries (
    path TEXT NOT NULL,
    role TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version INTEGER NOT NULL,
    content TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY (path, role, model, prompt_version)
);
CREATE TABLE IF NOT EXISTS file_hashes (
    path TEXT PRIMARY KEY,
    hash TEXT NOT NULL,
    lang TEXT,
    loc INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    reason TEXT,
    files_changed INTEGER DEFAULT 0,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    status TEXT
);
"""


class Cache:
    def __init__(self, root: Path) -> None:
        directory = Path(root) / ".epitaph"
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "cache.db"
        self.connection = sqlite3.connect(self.path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Cache:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # ------------------------------------------------------------- summaries

    def get_summary(self, path: str, role: str, model: str, prompt_version: int) -> str | None:
        row = self.connection.execute(
            "SELECT content FROM summaries WHERE path=? AND role=? AND model=? AND prompt_version=?",
            (path, role, model, prompt_version),
        ).fetchone()
        return row[0] if row else None

    def set_summary(
        self,
        path: str,
        role: str,
        model: str,
        prompt_version: int,
        content: str,
        generated_at: str,
    ) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO summaries VALUES (?, ?, ?, ?, ?, ?)",
            (path, role, model, prompt_version, content, generated_at),
        )
        self.connection.commit()

    # ------------------------------------------------------------ file hash

    def get_file_hash(self, path: str) -> str | None:
        row = self.connection.execute(
            "SELECT hash FROM file_hashes WHERE path=?", (path,)
        ).fetchone()
        return row[0] if row else None

    def set_file_hash(self, path: str, file_hash: str, lang: str, loc: int, now: str) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO file_hashes VALUES (?, ?, ?, ?, ?)",
            (path, file_hash, lang, loc, now),
        )
        self.connection.commit()

    def record_run(self, run: dict) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run["id"],
                run["started_at"],
                run.get("finished_at"),
                run.get("reason", ""),
                run.get("files_changed", 0),
                run.get("tokens_in", 0),
                run.get("tokens_out", 0),
                run.get("duration_ms", 0),
                run.get("status", "ok"),
            ),
        )
        self.connection.commit()
