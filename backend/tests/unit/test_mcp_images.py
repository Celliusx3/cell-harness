"""A tool's image: in words to a model that cannot see, and after the same words to one that can."""

from __future__ import annotations

import base64
import hashlib
import logging

from mcp.types import CallToolResult, ImageContent

from harness.images import IMAGE_MAX_BYTES, ImageService
from harness.llm import Image, Text, ToolMessage
from harness.mcp.tool import mcp_tool, outcome_of
from harness.prompts import IMAGE_TOO_LARGE
from harness.runtime.service import Runtime
from harness.tools import Ok, ReturnedImage
from tests.mcp_stub import DOT_PNG
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import drain, new_session, pipeline_for
from tests.unit.mcp_fakes import tool
from tests.unit.test_image_service import images_at

DOT = base64.b64decode(DOT_PNG)
DOT_SHA256 = hashlib.sha256(DOT).hexdigest()
IN_WORDS = f"[image image/png, {len(DOT_PNG)} base64 chars]"


def image_result(data: str = DOT_PNG, *, mime_type: str = "image/png") -> CallToolResult:
    return CallToolResult(content=[ImageContent(type="image", data=data, mime_type=mime_type)])


async def result_seen(images: ImageService | None, result: CallToolResult) -> ToolMessage:
    """The tool message the model's next request carries once a tool returned `result`."""

    async def call(name: str, arguments: dict) -> CallToolResult:
        return result

    model = SteppedClient(calls_tool("srv__snap"), completed("seen"))
    runtime = Runtime(
        model="m",
        client=model,
        images=images,
        tools=pipeline_for(mcp_tool(server="srv", tool=tool("snap"), call=call)),
    )
    await drain(runtime.run("look", session=new_session(), bot_id="b"))
    (message,) = [m for m in model.seen_per_call[1] if isinstance(m, ToolMessage)]
    return message


async def test_without_vision_a_tool_s_image_is_still_described_in_words() -> None:
    message = await result_seen(None, image_result())

    assert message.content == (Text(text=IN_WORDS),)


async def test_with_vision_the_image_follows_the_same_words_and_is_kept(tmp_path) -> None:
    message = await result_seen(images_at(tmp_path), image_result())

    assert message.content == (
        Text(text=IN_WORDS),
        Image(media_type="image/png", sha256=DOT_SHA256, size=len(DOT)),
    )
    assert (tmp_path / f"{DOT_SHA256}.png").read_bytes() == DOT


async def test_an_image_over_five_megabytes_is_not_sent_and_the_result_says_so(tmp_path) -> None:
    too_big = base64.b64encode(bytes(IMAGE_MAX_BYTES + 1)).decode()

    message = await result_seen(images_at(tmp_path), image_result(too_big))

    assert not [block for block in message.content if isinstance(block, Image)]
    note = IMAGE_TOO_LARGE.format(size=IMAGE_MAX_BYTES + 1, limit=IMAGE_MAX_BYTES)
    assert message.content[-1] == Text(text=note)
    assert list(tmp_path.iterdir()) == []


async def test_an_image_of_a_type_no_model_is_sent_stays_in_words(tmp_path, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="harness.images"):
        message = await result_seen(images_at(tmp_path), image_result(mime_type="image/bmp"))

    assert message.content == (Text(text=f"[image image/bmp, {len(DOT_PNG)} base64 chars]"),)
    assert "image/bmp" in caplog.text


def test_a_tool_s_image_is_carried_decoded_beside_its_words() -> None:
    outcome = outcome_of(image_result(), name="srv__snap", server="srv", resource_uri=None)

    assert isinstance(outcome, Ok)
    assert outcome.text == IN_WORDS
    assert outcome.images == (ReturnedImage(media_type="image/png", data=DOT),)


def test_an_image_whose_data_is_not_base64_is_dropped_with_a_warning(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="harness.mcp"):
        outcome = outcome_of(
            image_result("not base64!"), name="srv__snap", server="srv", resource_uri=None
        )

    assert isinstance(outcome, Ok)
    assert outcome.images == ()
    assert "dropped an image srv__snap returned" in caplog.text
