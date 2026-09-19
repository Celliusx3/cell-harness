"""The model's window, read from the endpoint."""

from __future__ import annotations

import json

import httpx

from harness.llm.adapters import models as models_module
from harness.llm.adapters.models import context_length
from tests.unit.test_openai_adapter import settings

# ilmu serves the field on `/models`, not on `/models/{id}` (404).
ILMU = {
    "data": [
        {"id": "glm-ocr", "context_length": 32768, "max_completion_tokens": 32768},
        {"id": "m", "context_length": 1000000, "max_completion_tokens": 128000},
    ]
}
LM_STUDIO = {"data": [{"id": "m", "object": "model", "owned_by": "organization_owner"}]}


_REAL = httpx.AsyncClient


def patched(monkeypatch, handler) -> None:
    def factory(**kwargs):
        return _REAL(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(models_module.httpx, "AsyncClient", factory)


async def test_reads_the_configured_models_context_length(monkeypatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=json.dumps(ILMU).encode())

    patched(monkeypatch, handler)
    assert await context_length(settings()) == 1000000
    assert seen[0].url == "https://x/v1/models"
    assert seen[0].headers["authorization"] == "Bearer k"


async def test_an_endpoint_that_does_not_say_yields_none(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(LM_STUDIO).encode())

    patched(monkeypatch, handler)
    assert await context_length(settings()) is None


async def test_a_missing_model_a_bad_body_and_a_dead_endpoint_yield_none(monkeypatch) -> None:
    for handler in (
        lambda r: httpx.Response(200, content=b'{"data":[{"id":"other","context_length":5}]}'),
        lambda r: httpx.Response(200, content=b"not json"),
        lambda r: httpx.Response(200, content=b'{"data":[{"id":"m","context_length":"big"}]}'),
        lambda r: httpx.Response(500, content=b""),
    ):
        patched(monkeypatch, handler)
        assert await context_length(settings()) is None

    def dead(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    patched(monkeypatch, dead)
    assert await context_length(settings()) is None
