"""Worker único con cancelación y sin backlog."""

from __future__ import annotations

import threading
from collections.abc import Callable
from queue import Empty, Full, Queue


class Worker:
    def __init__(self, job: Callable[[], None]) -> None:
        self.job = job
        self._queue: Queue[None] = Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = threading.Event()
        self.cancel = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._queue.get(timeout=0.2)
            except Empty:
                continue
            self._running.set()
            self.cancel.clear()
            try:
                self.job()
            finally:
                self._running.clear()
                self._queue.task_done()

    def submit(self) -> bool:
        """Encola un run; devuelve False si ya hay uno pendiente."""
        try:
            self._queue.put_nowait(None)
            return True
        except Full:
            return False

    @property
    def busy(self) -> bool:
        return self._running.is_set() or not self._queue.empty()

    def stop(self) -> None:
        self._stop.set()
        self.cancel.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
