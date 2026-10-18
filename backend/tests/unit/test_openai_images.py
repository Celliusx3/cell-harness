"""Images on the wire: data URLs after the words, read just before the request, never raising."""

from __future__ import annotations

import base64
import hashlib
import json
import logging

import httpx

from harness.llm import (
    AssistantMessage,
    Image,
    Message,
    Text,
    ToolCall,
    ToolMessage,
    ToolReference,
    UserMessage,
)
from harness.llm.adapters import ImageReader
from harness.prompts import IMAGE_NOT_SHOWN, IMAGES_FOLLOW, REFERENCES_NOTE, TOOL_IMAGES
from tests.mcp_stub import DOT_PNG
from tests.unit.test_image_service import RETURNED_DOT, images_at
from tests.unit.test_openai_adapter import collect, nothing_kept, sse

DOT = base64.b64decode(DOT_PNG)
DOT_URL = f"data:image/png;base64,{DOT_PNG}"
CALL = ToolCall(id="c1", name="srv__snap", arguments="{}")
ASKED = AssistantMessage(content="", tool_calls=(CALL,))


async def sent(monkeypatch, messages: list[Message], read_image: ImageReader) -> bytes:
    """The raw body the adapter posts for `messages`."""
    captured: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.content)
        return httpx.Response(200, content=sse("[DONE]"))

    await collect(monkeypatch, handler, messages=messages, read_image=read_image)
    return captured[0]


async def wired(monkeypatch, messages: list[Message], read_image: ImageReader) -> list[dict]:
    return json.loads(await sent(monkeypatch, messages, read_image))["messages"]


async def test_a_tool_s_image_rides_a_user_message_after_its_result(monkeypatch, tmp_path) -> None:
    images = images_at(tmp_path)
    (image,) = images.of_result((RETURNED_DOT,))
    result = ToolMessage(tool_call_id="c1", content=(Text(text="shot"), image))

    *_, tool, after = await wired(
        monkeypatch, [UserMessage(content="look"), ASKED, result], images.read
    )

    assert tool == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": "shot\n\n" + IMAGES_FOLLOW.format(count=1),
    }
    assert after == {
        "role": "user",
        "content": [
            {"type": "text", "text": TOOL_IMAGES},
            {"type": "image_url", "image_url": {"url": DOT_URL}},
        ],
    }


async def test_images_wait_until_every_result_of_the_step_is_sent(monkeypatch, tmp_path) -> None:
    images = images_at(tmp_path)
    (image,) = images.of_result((RETURNED_DOT,))
    second = ToolCall(id="c2", name="srv__snap", arguments="{}")
    messages: list[Message] = [
        AssistantMessage(content="", tool_calls=(CALL, second)),
        ToolMessage(tool_call_id="c1", content=(Text(text="one"), image)),
        ToolMessage(tool_call_id="c2", content=(Text(text="two"), image)),
        UserMessage(content="next"),
    ]

    wire = await wired(monkeypatch, messages, images.read)

    assert [m["role"] for m in wire] == ["assistant", "tool", "tool", "user", "user"]
    assert len(wire[3]["content"]) == 3
    assert wire[4] == {"role": "user", "content": "next"}


async def test_the_person_s_image_rides_their_message_after_the_text(monkeypatch, tmp_path) -> None:
    images = images_at(tmp_path)
    (image,) = images.of_result((RETURNED_DOT,))

    (person,) = await wired(
        monkeypatch, [UserMessage(content="look", images=(image,))], images.read
    )

    assert person == {
        "role": "user",
        "content": [
            {"type": "text", "text": "look"},
            {"type": "image_url", "image_url": {"url": DOT_URL}},
        ],
    }


async def test_a_result_s_references_are_spelled_out_beside_its_image(
    monkeypatch, tmp_path
) -> None:
    images = images_at(tmp_path)
    (image,) = images.of_result((RETURNED_DOT,))
    blocks = (Text(text="shot"), ToolReference(tool_name="srv__act"), image)

    _, tool, _ = await wired(
        monkeypatch, [ASKED, ToolMessage(tool_call_id="c1", content=blocks)], images.read
    )

    assert tool["content"] == "\n\n".join(
        ["shot", REFERENCES_NOTE.format(names="srv__act"), IMAGES_FOLLOW.format(count=1)]
    )


async def test_without_images_both_are_sent_byte_for_byte_as_before(monkeypatch) -> None:
    messages: list[Message] = [
        UserMessage(content="hi"),
        ASKED,
        ToolMessage(tool_call_id="c1", content="ok"),
    ]

    body = await sent(monkeypatch, messages, nothing_kept)

    before = (
        '"messages":[{"role":"user","content":"hi"},'
        '{"role":"assistant","content":"","tool_calls":[{"id":"c1","type":"function",'
        '"function":{"name":"srv__snap","arguments":"{}"}}]},'
        '{"role":"tool","tool_call_id":"c1","content":"ok"}]'
    )
    assert before.encode() in body


async def test_an_image_whose_bytes_are_gone_is_sent_as_the_note(
    monkeypatch, tmp_path, caplog
) -> None:
    gone = Image(media_type="image/png", sha256=hashlib.sha256(DOT).hexdigest(), size=len(DOT))
    messages: list[Message] = [
        UserMessage(content="look", images=(gone,)),
        ASKED,
        ToolMessage(tool_call_id="c1", content=(Text(text="shot"), gone)),
    ]

    with caplog.at_level(logging.WARNING, logger="harness.images"):
        person, _, tool = await wired(monkeypatch, messages, images_at(tmp_path).read)

    assert person == {"role": "user", "content": f"look\n{IMAGE_NOT_SHOWN}"}
    assert tool["content"] == f"shot\n\n{IMAGE_NOT_SHOWN}"
    assert "could not be read" in caplog.text
