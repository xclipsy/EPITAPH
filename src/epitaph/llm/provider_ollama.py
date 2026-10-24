"""Cliente mínimo para Ollama (HTTP, sin SDK)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from ..errors import LLMUnavailable


class OllamaProvider:
    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------ probe

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=1.5) as client:
                return client.get(f"{self.base_url}/api/tags").status_code == 200
        except httpx.HTTPError:
            return False

    def list_models(self) -> list[dict]:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise LLMUnavailable(
                f"No se pudo conectar con Ollama en {self.base_url}",
                hint="ejecuta `ollama serve` o configura [llm].base_url",
            ) from exc
        return data.get("models", [])

    def show(self, model: str) -> dict:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(f"{self.base_url}/api/show", json={"model": model})
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError:
            return {}

    def pull(self, model: str) -> Iterator[dict]:
        with httpx.Client(timeout=None) as client:
            with client.stream(
                "POST", f"{self.base_url}/api/pull", json={"model": model, "stream": True}
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        yield httpx.Response(200, content=line).json()

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
        on_token=None,
    ) -> str:
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
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(f"{self.base_url}/api/chat", json=payload)
                    response.raise_for_status()
                    return response.json().get("message", {}).get("content", "")

            chunks: list[str] = []
            with httpx.Client(timeout=None) as client:
                with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        event = httpx.Response(200, content=line).json()
                        token = event.get("message", {}).get("content", "")
                        if token:
                            chunks.append(token)
                            on_token(token)
                        if event.get("done"):
                            break
            return "".join(chunks)
        except httpx.HTTPError as exc:
            raise LLMUnavailable(
                f"falló la inferencia con el modelo '{model}'",
                hint="comprueba `ollama list` y la memoria disponible",
            ) from exc
