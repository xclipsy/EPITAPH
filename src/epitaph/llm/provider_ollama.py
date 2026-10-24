"""Cliente mínimo para Ollama (HTTP, sin SDK)."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx

from ..errors import LLMUnavailable

AVAILABILITY_TTL = 5.0
MODELS_TTL = 10.0


class OllamaProvider:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.last_stats: dict[str, float | int | None] = {}
        self._transport = transport
        self._client: httpx.Client | None = None
        self._lock = threading.Lock()
        self._available = False
        self._available_at = 0.0
        self._models: list[dict] = []
        self._models_at = 0.0
        self._models_error = ""

    # --------------------------------------------------------------- transport

    def _http(self) -> httpx.Client:
        """Cliente reutilizado: evita reabrir conexiones en cada mensaje del chat."""
        with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.Client(
                    base_url=self.base_url,
                    timeout=httpx.Timeout(self.timeout, connect=2.0),
                    limits=httpx.Limits(max_keepalive_connections=4, max_connections=8),
                    transport=self._transport,
                )
            return self._client

    def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            self._client.close()
        self._client = None

    def __enter__(self) -> OllamaProvider:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ------------------------------------------------------------------ probe

    def is_available(self, *, fresh: bool = False) -> bool:
        """Sonda barata y cacheada: no bloquea el chat si Ollama está caído."""
        now = time.monotonic()
        if not fresh and now - self._available_at < AVAILABILITY_TTL:
            return self._available
        try:
            response = self._http().get("/api/tags", timeout=2.0)
            self._available = response.status_code == 200
        except httpx.HTTPError:
            self._available = False
        self._available_at = now
        return self._available

    def list_models(self, *, fresh: bool = False) -> list[dict]:
        now = time.monotonic()
        if not fresh and now - self._models_at < MODELS_TTL:
            if self._models_error:
                raise LLMUnavailable(
                    self._models_error,
                    hint="ejecuta `ollama serve` o configura [llm].base_url",
                )
            return self._models
        try:
            response = self._http().get("/api/tags", timeout=5.0)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            self._models = []
            self._models_error = f"No se pudo conectar con Ollama en {self.base_url}"
            self._models_at = now
            self._available = False
            self._available_at = now
            raise LLMUnavailable(
                self._models_error,
                hint="ejecuta `ollama serve` o configura [llm].base_url",
            ) from exc
        self._models = data.get("models", [])
        self._models_at = now
        self._models_error = ""
        self._available = True
        self._available_at = now
        return self._models

    def show(self, model: str) -> dict:
        try:
            response = self._http().post("/api/show", json={"model": model}, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return {}

    def pull(self, model: str) -> Iterator[dict]:
        with self._http().stream(
            "POST",
            "/api/pull",
            json={"model": model, "stream": True},
            timeout=None,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    yield json.loads(line)

    def warmup(self, model: str, *, keep_alive: str = "30m") -> None:
        """Carga el modelo en segundo plano: la primera respuesta llega antes."""
        def _run() -> None:
            try:
                self.chat(
                    model,
                    [{"role": "user", "content": "ok"}],
                    num_ctx=512,
                    num_predict=1,
                    keep_alive=keep_alive,
                    record_stats=False,
                )
            except Exception:  # noqa: BLE001 - el warmup nunca debe romper el chat
                pass

        threading.Thread(target=_run, daemon=True, name="epitaph-warmup").start()

    # ------------------------------------------------------------------- chat

    def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        num_ctx: int = 4096,
        num_predict: int = 600,
        temperature: float = 0.2,
        num_thread: int | None = None,
        keep_alive: str = "30m",
        on_token: Callable[[str], bool | None] | None = None,
        record_stats: bool = True,
    ) -> str:
        """Genera una respuesta. Con ``on_token`` transmite cada fragmento.

        El callback puede devolver ``False`` para cancelar la generación.
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": on_token is not None,
            "keep_alive": keep_alive,
            "options": {
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                "temperature": temperature,
            },
        }
        if num_thread:
            payload["options"]["num_thread"] = num_thread

        try:
            if on_token is None:
                started = time.monotonic()
                response = self._http().post("/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                content = data.get("message", {}).get("content", "")
                if record_stats:
                    self._remember_stats(
                        data, started=started, first_token=started, chars=len(content)
                    )
                return content

            return self._stream_chat(payload, on_token, record_stats=record_stats)
        except httpx.HTTPError as exc:
            raise LLMUnavailable(
                f"falló la inferencia con el modelo '{model}'",
                hint="comprueba `ollama list` y la memoria disponible",
            ) from exc

    def _stream_chat(
        self,
        payload: dict[str, Any],
        on_token: Callable[[str], bool | None],
        *,
        record_stats: bool = True,
    ) -> str:
        started = time.monotonic()
        first_token: float | None = None
        chunks: list[str] = []

        with self._http().stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                token = event.get("message", {}).get("content", "")
                if token:
                    if first_token is None:
                        first_token = time.monotonic()
                    chunks.append(token)
                    if on_token(token) is False:
                        break
                if event.get("done"):
                    if record_stats:
                        self._remember_stats(
                            event,
                            started=started,
                            first_token=first_token or started,
                            chars=sum(len(chunk) for chunk in chunks),
                        )
                    break
        return "".join(chunks)

    def _remember_stats(
        self, event: dict, *, started: float, first_token: float, chars: int
    ) -> None:
        """Guarda métricas del último chat para que la UI muestre tok/s reales."""
        eval_count = int(event.get("eval_count") or 0)
        prompt_tokens = int(event.get("prompt_eval_count") or 0)
        eval_seconds = (event.get("eval_duration") or 0) / 1e9
        estimated = max(1, chars // 4)
        self.last_stats = {
            "tokens": eval_count or (estimated if chars else 0),
            "prompt_tokens": prompt_tokens,
            "total_s": round(time.monotonic() - started, 2),
            "first_token_s": round(max(0.0, first_token - started), 2),
            "tok_per_s": round(eval_count / eval_seconds, 1) if eval_seconds > 0 else None,
        }
