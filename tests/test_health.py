from __future__ import annotations

from epitaph.errors import LLMUnavailable
from epitaph.llm.health import probe


class FakeProvider:
    def __init__(
        self,
        *,
        available: bool = True,
        models: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        self.base_url = "http://localhost:11434"
        self.available = available
        self.models = models or []
        self.error = error

    def is_available(self) -> bool:
        return self.available

    def list_models(self) -> list[dict]:
        if self.error:
            raise LLMUnavailable(self.error)
        return [{"name": name} for name in self.models]


def test_probe_ready_with_models() -> None:
    health = probe(FakeProvider(models=["qwen2.5-coder:3b"]))  # type: ignore[arg-type]

    assert health.ready is True
    assert health.reachable is True
    assert health.models == ("qwen2.5-coder:3b",)
    assert "1 modelo" in health.state


def test_probe_without_server() -> None:
    health = probe(FakeProvider(available=False))  # type: ignore[arg-type]

    assert health.ready is False
    assert health.reachable is False
    assert health.state == "servidor no detectado"
    assert "api/tags" in health.error


def test_probe_without_models() -> None:
    health = probe(FakeProvider(models=[]))  # type: ignore[arg-type]

    assert health.ready is False
    assert health.reachable is True
    assert health.state == "servidor activo · sin modelos"


def test_probe_reports_listing_error() -> None:
    health = probe(FakeProvider(error="falló el listado"))  # type: ignore[arg-type]

    assert health.ready is False
    assert health.reachable is False
    assert health.error == "falló el listado"
