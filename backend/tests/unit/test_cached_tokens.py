"""Each reply's usage keeps how many of its input tokens the provider read from its cache."""

from __future__ import annotations

import json

import httpx

from harness.llm import Usage
from harness.llm.adapters.openai import client as adapter_module
from harness.runtime.service import Runtime
from harness.session.domain.models import AssistantMessageEvent
from tests.unit.fakes import OneModel
from tests.unit.helpers import new_session, no_images
from tests.unit.test_openai_adapter import client_over, collect, delta, sse

OPENROUTER_USAGE = {
    "prompt_tokens": 10339,
    "completion_tokens": 12,
    "prompt_tokens_details": {"cached_tokens": 10318, "cache_write_tokens": 0},
}


def _replying(usage: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        frame = json.dumps({"choices": [], "usage": usage})
        return httpx.Response(200, content=sse(delta("ok"), frame, "[DONE]"))

    return handler


async def test_cached_tokens_are_read_beside_all_input_tokens(monkeypatch) -> None:
    events = await collect(monkeypatch, _replying(OPENROUTER_USAGE))

    assert events[-1].usage == Usage(
        input_tokens=10339, output_tokens=12, cached_input_tokens=10318
    )


async def test_a_provider_that_reports_no_cache_gives_none(monkeypatch) -> None:
    events = await collect(monkeypatch, _replying({"prompt_tokens": 7, "completion_tokens": 2}))

    assert events[-1].usage == Usage(input_tokens=7, output_tokens=2, cached_input_tokens=None)


async def test_a_turn_logs_the_cached_tokens_its_reply_reported(monkeypatch) -> None:
    factory, client = client_over(_replying(OPENROUTER_USAGE))
    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", factory)
    runtime = Runtime(models=OneModel(client), images=no_images())
    session = new_session()

    [_ async for _ in runtime.run("hi", session=session, bot_id="b")]

    reply = next(e for e in session.events() if isinstance(e, AssistantMessageEvent))
    assert reply.usage is not None
    assert reply.usage.cached_input_tokens == 10318


def test_a_reply_logged_before_cached_tokens_still_loads() -> None:
    line = {
        "type": "assistant/message",
        "turn": 0,
        "step": 0,
        "message": {"role": "assistant", "content": "ok"},
        "usage": {"input_tokens": 7, "output_tokens": 2},
    }

    loaded = AssistantMessageEvent.model_validate(line)

    assert loaded.usage == Usage(input_tokens=7, output_tokens=2, cached_input_tokens=None)
