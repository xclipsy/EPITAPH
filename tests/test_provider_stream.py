from __future__ import annotations

import json

import httpx

from epitaph.llm.provider_ollama import OllamaProvider


def _ndjson(events: list[dict]) -> bytes:
    return ("\n".join(json.dumps(event) for event in events) + "\n").encode()


def test_chat_streams_tokens_in_order() -> None:
    events = [
        {"message": {"content": "ho"}, "done": False},
        {"message": {"content": "la"}, "done": False},
        {
            "message": {"content": " mundo"},
            "done": True,
            "eval_count": 3,
            "eval_duration": 1_500_000_000,
            "prompt_eval_count": 12,
        },
    ]
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=_ndjson(events)))
    provider = OllamaProvider(transport=transport)

    seen: list[str] = []
    text = provider.chat("m", [{"role": "user", "content": "x"}], on_token=seen.append)

    assert text == "hola mundo"
    assert seen == ["ho", "la", " mundo"]
    assert provider.last_stats["tokens"] == 3
    assert provider.last_stats["prompt_tokens"] == 12
    assert provider.last_stats["tok_per_s"] == 2.0
    provider.close()


def test_on_token_can_cancel_generation() -> None:
    events = [
        {"message": {"content": "uno"}, "done": False},
        {"message": {"content": "dos"}, "done": False},
        {"message": {"content": "tres"}, "done": True},
    ]
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=_ndjson(events)))
    provider = OllamaProvider(transport=transport)

    def stop_after_first(token: str) -> bool:
        return False

    text = provider.chat("m", [{"role": "user", "content": "x"}], on_token=stop_after_first)

    assert text == "uno"
    provider.close()


def test_probe_and_models_are_cached() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:3b"}]})

    provider = OllamaProvider(transport=httpx.MockTransport(handler))

    assert provider.is_available() is True
    assert provider.is_available() is True
    assert provider.list_models() == [{"name": "qwen2.5-coder:3b"}]
    assert provider.list_models() == [{"name": "qwen2.5-coder:3b"}]
    # una sonda + una consulta de modelos; las siguientes se sirven de caché
    assert calls.count("/api/tags") == 2

    provider.is_available(fresh=True)
    assert calls.count("/api/tags") == 3
    provider.close()
