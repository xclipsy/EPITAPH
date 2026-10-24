"""Watcher de cambios: watchdog si está disponible, polling como fallback."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from ..analyzers.scanner import Scanner


class Watcher:
    def __init__(
        self,
        root: Path,
        on_change: Callable[[list[str]], None],
        poll_interval: float = 2.0,
    ) -> None:
        self.root = Path(root)
        self.on_change = on_change
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._observer = None

    def start(self) -> None:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            watcher = self

            class Handler(FileSystemEventHandler):
                def on_any_event(self, event):  # type: ignore[override]
                    if event.is_directory:
                        return
                    try:
                        rel = Path(event.src_path).resolve().relative_to(watcher.root).as_posix()
                    except ValueError:
                        return
                    if rel.startswith((".git/", ".epitaph/")):
                        return
                    watcher.on_change([rel])

            self._observer = Observer()
            self._observer.schedule(Handler(), str(self.root), recursive=True)
            self._observer.start()
            return
        except Exception:
            self._observer = None
            self._start_polling()

    def _start_polling(self) -> None:
        def loop() -> None:
            scanner = Scanner(self.root)
            seen: dict[str, float] = {}
            while not self._stop.wait(self.poll_interval):
                changed: list[str] = []
                for path in scanner.iter_files():
                    try:
                        stamp = path.stat().st_mtime
                    except OSError:
                        continue
                    rel = scanner.rel(path)
                    if seen.get(rel) != stamp:
                        if rel in seen:
                            changed.append(rel)
                        seen[rel] = stamp
                if changed:
                    self.on_change(changed)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2)
        if self._thread is not None:
            self._thread.join(timeout=2)
