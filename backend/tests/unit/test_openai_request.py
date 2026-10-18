"""The request the adapter sends: its address, its key, its body and its messages."""

from __future__ import annotations

import json

import httpx

from harness.llm.adapters.openai_wire import wire_messages
from harness.llm.messages import SystemMessage
from tests.unit.test_openai_adapter import collect, sse


async def test_the_request_goes_to_chat_completions_with_the_key_and_the_whole_body(
    monkeypatch,
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, content=sse("[DONE]"))

    await collect(monkeypatch, handler)

    assert str(sent[0].url) == "https://x/v1/chat/completions"
    assert sent[0].headers["authorization"] == "Bearer k"
    assert json.loads(sent[0].content) == {
        "model": "m",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 1.0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }


def test_a_system_message_is_sent_as_its_role_and_its_text() -> None:
    assert wire_messages([SystemMessage(content="be brief")], {}) == [
        {"role": "system", "content": "be brief"}
    ]
