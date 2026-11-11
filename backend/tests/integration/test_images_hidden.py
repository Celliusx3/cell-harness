"""Old images are hidden in logged blocks past the request's limit, and never come back."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx
import pytest

from harness.llm import AssistantMessage, Failed, Image, UserMessage
from harness.llm.adapters import OpenAIClient
from harness.llm.adapters.openai import client as adapter_module
from harness.runtime.service import Runtime
from harness.session.images import ImagesHidden
from harness.session.log import Session
from harness.session.models import (
    AssistantChunk,
    AssistantMessageEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from tests.unit.fakes import OneModel
from tests.unit.helpers import new_session, no_images
from tests.unit.test_openai_adapter import delta, settings, sse

MIB = 1024 * 1024
PAGE_BYTES = MIB
TEN_MIB_OF_BASE64 = 10 * MIB


def _page(number: int) -> Image:
    return Image(media_type="image/png", sha256=f"{number:064x}", size=PAGE_BYTES)


def _base64_size(size: int) -> int:
    return -(-size // 3) * 4


def _bytes_of(image: Image) -> bytes:
    return bytes(image.size)


@dataclass
class Provider:
    """An endpoint that answers "ok" and keeps every request body it was sent."""

    bodies: list[dict] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(json.loads(request.content))
        return httpx.Response(200, content=sse(delta("ok"), "[DONE]"))


@pytest.fixture
def provider(monkeypatch) -> Provider:
    endpoint = Provider()
    real = httpx.AsyncClient

    def factory(**kwargs):
        return real(transport=httpx.MockTransport(endpoint), **kwargs)

    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", factory)
    return endpoint


def _runtime() -> Runtime:
    client = OpenAIClient(settings(), read_image=_bytes_of)
    return Runtime(models=OneModel(client, vision=True), images=no_images())


def _with_pages(session: Session, pages: range) -> Session:
    """`session` with one past turn per page, each the person's page and an "ok"."""
    for number in pages:
        turn = session.next_turn()
        session.append(TurnStart(turn=turn, bot_id="b"))
        message = UserMessage(content=f"page {number}", images=(_page(number),))
        session.append(UserMessageEvent(turn=turn, message=message))
        reply = AssistantMessage(content="ok")
        session.append(AssistantMessageEvent(turn=turn, step=0, message=reply))
        session.append(TurnEnd(turn=turn, reason="completed"))
    return session


def _hides(session: Session) -> list[ImagesHidden]:
    return [event for event in session.events() if isinstance(event, ImagesHidden)]


def _image_parts(body: dict) -> list[dict]:
    return [
        part
        for message in body["messages"]
        if isinstance(message["content"], list)
        for part in message["content"]
        if part["type"] == "image_url"
    ]


def _image_bytes_sent(body: dict) -> int:
    return sum(len(part["image_url"]["url"].split(",", 1)[1]) for part in _image_parts(body))


async def _turn(runtime: Runtime, session: Session, text: str) -> None:
    [_ async for _ in runtime.run(text, session=session, bot_id="b")]


async def test_images_under_the_limit_are_all_sent_and_none_hidden(provider) -> None:
    session = _with_pages(new_session(), range(10))

    await _turn(_runtime(), session, "next")

    assert _hides(session) == []
    assert len(_image_parts(provider.bodies[-1])) == 10


async def test_past_the_limit_the_oldest_block_is_hidden_once_then_sent(provider) -> None:
    session = _with_pages(new_session(), range(25))

    await _turn(_runtime(), session, "next")

    [hide] = _hides(session)
    [sent] = provider.bodies
    assert _image_bytes_sent(sent) <= 20 * MIB
    assert len(_image_parts(sent)) == 25 - hide.through
    assert hide.through * _base64_size(PAGE_BYTES) >= TEN_MIB_OF_BASE64


async def test_between_two_hides_each_request_starts_with_the_last(provider) -> None:
    runtime = _runtime()
    session = _with_pages(new_session(), range(25))
    await _turn(runtime, session, "next")

    for number in range(25, 28):
        _with_pages(session, range(number, number + 1))
        await _turn(runtime, session, "next")

    assert len(_hides(session)) == 1
    for before, after in zip(provider.bodies, provider.bodies[1:], strict=False):
        assert after["messages"][: len(before["messages"])] == before["messages"]


async def test_hidden_images_stay_hidden_on_a_model_that_sees_more(provider) -> None:
    session = _with_pages(new_session(), range(25))
    await _turn(_runtime(), session, "next")
    [hide] = _hides(session)

    roomy = _runtime().request_messages(session, sees_images=True)

    shown = sum(len(message.images) for message in roomy if isinstance(message, UserMessage))
    assert shown == 25 - hide.through


async def test_a_hide_leaves_no_failure_in_the_chat(provider) -> None:
    session = _with_pages(new_session(), range(25))

    await _turn(_runtime(), session, "next")

    chunks = [e.chunk for e in session.events() if isinstance(e, AssistantChunk)]
    assert [chunk for chunk in chunks if isinstance(chunk, Failed)] == []
