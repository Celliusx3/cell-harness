"""The provider's refusal of an oversized request, recognised — or not."""

from __future__ import annotations

import httpx
import pytest

from harness.llm.adapters.errors import classify
from harness.llm.stream import CONTEXT_WINDOW_EXCEEDED, Failed
from tests.unit.test_openai_adapter import collect

ILMU_GLM_OCR = (
    '{"error":{"message":"This model\'s maximum context length is 32768 tokens. However, '
    'your request would use ~40014 tokens (prompt plus requested max_tokens).",'
    '"type":"invalid_request_error","param":"messages","code":"context_length_exceeded"}}'
)
LM_STUDIO = '{"error":"Context length exceeded"}'
ILMU_GENERIC = (
    '{"error":{"type":"invalid_request_error","param":null,"code":"invalid_request",'
    '"message":"The request was invalid and could not be processed by the model."}}'
)


@pytest.mark.parametrize("body", [ILMU_GLM_OCR, LM_STUDIO])
def test_the_two_probed_overflow_shapes_are_recognised(body: str) -> None:
    assert classify(body) == CONTEXT_WINDOW_EXCEEDED


@pytest.mark.parametrize(
    "body",
    [ILMU_GENERIC, '{"error":"rate limited"}', "not json", "", '{"error":{"code":null}}', "[]"],
)
def test_anything_else_is_not_classified(body: str) -> None:
    assert classify(body) is None


async def test_a_recognised_400_reaches_the_loop_as_a_coded_failure(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, content=LM_STUDIO.encode())

    events = await collect(monkeypatch, handler)

    assert len(events) == 1
    assert isinstance(events[0], Failed)
    assert events[0].code == CONTEXT_WINDOW_EXCEEDED
    assert "Context length exceeded" in events[0].reason


async def test_an_unrecognised_400_carries_no_code(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, content=ILMU_GENERIC.encode())

    events = await collect(monkeypatch, handler)

    assert isinstance(events[0], Failed)
    assert events[0].code is None
