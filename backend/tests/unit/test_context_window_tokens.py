"""The model's window, read from the endpoint."""

from __future__ import annotations

import json

import httpx

from harness.config.sections import CompactionSettings
from harness.llm.adapters import context_window_tokens
from harness.llm.adapters.openai import client as adapter_module
from harness.web.runtime import context_window
from tests.unit.test_openai_adapter import settings

# ilmu serves the field on `/models`, not on `/models/{id}` (404).
ILMU = {
    "data": [
        {"id": "glm-ocr", "context_length": 32768, "max_completion_tokens": 32768},
        {"id": "m", "context_length": 1000000, "max_completion_tokens": 128000},
    ]
}
LM_STUDIO = {"data": [{"id": "m", "object": "model", "owned_by": "organization_owner"}]}


_REAL = httpx.Client


def patched(monkeypatch, handler) -> None:
    def factory(**kwargs):
        return _REAL(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(adapter_module.httpx, "Client", factory)


def test_reads_the_configured_models_context_length(monkeypatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=json.dumps(ILMU).encode())

    patched(monkeypatch, handler)
    assert context_window_tokens(settings()) == 1000000
    assert seen[0].url == "https://x/v1/models"
    assert seen[0].headers["authorization"] == "Bearer k"


def test_an_endpoint_that_does_not_say_yields_none(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(LM_STUDIO).encode())

    patched(monkeypatch, handler)
    assert context_window_tokens(settings()) is None


def test_a_window_that_is_not_positive_is_not_trusted(monkeypatch) -> None:
    for length in (0, -1):
        body = json.dumps({"data": [{"id": "m", "context_length": length}]}).encode()
        patched(monkeypatch, lambda r, body=body: httpx.Response(200, content=body))
        assert context_window_tokens(settings()) is None


def test_a_missing_model_a_bad_body_and_a_dead_endpoint_yield_none(monkeypatch) -> None:
    for handler in (
        lambda r: httpx.Response(200, content=b'{"data":[{"id":"other","context_length":5}]}'),
        lambda r: httpx.Response(200, content=b"not json"),
        lambda r: httpx.Response(200, content=b'{"data":[{"id":"m","context_length":"big"}]}'),
        lambda r: httpx.Response(500, content=b""),
    ):
        patched(monkeypatch, handler)
        assert context_window_tokens(settings()) is None

    def dead(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    patched(monkeypatch, dead)
    assert context_window_tokens(settings()) is None


def test_a_configured_window_wins_and_the_endpoint_is_not_asked(monkeypatch) -> None:
    seen: list[httpx.Request] = []
    patched(monkeypatch, lambda r: seen.append(r) or httpx.Response(200, json=ILMU))

    assert context_window(CompactionSettings(context_tokens=4096), settings()) == 4096
    assert seen == []


def test_with_no_configured_window_the_endpoint_says_it(monkeypatch) -> None:
    patched(monkeypatch, lambda r: httpx.Response(200, json=ILMU))
    assert context_window(CompactionSettings(context_tokens=None), settings()) == 1000000

    patched(monkeypatch, lambda r: httpx.Response(200, json=LM_STUDIO))
    assert context_window(CompactionSettings(context_tokens=None), settings()) is None
