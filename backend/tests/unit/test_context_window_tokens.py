"""The model's window, read from the endpoint."""

from __future__ import annotations

import json

import httpx
from pydantic import SecretStr

from harness.config.sections import CompactionSettings
from harness.config.settings import Settings
from harness.llm.adapters import context_window_tokens
from harness.llm.adapters.openai import client as adapter_module
from harness.secrets import DEFAULT_MODEL_CREDENTIAL
from harness.secrets.models.details import ModelDetails
from harness.web.server import _resolve_context_tokens
from tests.unit.test_openai_adapter import settings
from tests.webapp import secrets_in

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


async def test_the_window_is_found_from_inside_a_running_loop(tmp_path, monkeypatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=json.dumps(ILMU).encode())

    def client(**kwargs):
        return _REAL(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(adapter_module.httpx, "Client", client)
    unset = Settings.model_construct(
        llm=settings(), compaction=CompactionSettings(context_tokens=None)
    )

    keyring = secrets_in(tmp_path)
    default = ModelDetails(base_url="https://default.example/v1", model="m")
    keyring.add_credential(DEFAULT_MODEL_CREDENTIAL, default, SecretStr("sk-default-window"))

    assert _resolve_context_tokens(unset, keyring) == 1000000
    assert seen[0].url == "https://default.example/v1/models"
    assert seen[0].headers["authorization"] == "Bearer sk-default-window"
