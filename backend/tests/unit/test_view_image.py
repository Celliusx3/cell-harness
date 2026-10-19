"""`view_image` shows the model an image file kept with the chat."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path

from harness.config.settings import Settings
from harness.images import IMAGE_MAX_BYTES
from harness.llm import Image, ToolCall
from harness.mcp.service import McpService
from harness.runtime.service import Runtime
from harness.session.models import ToolResultEvent
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools import INVALID_ARGUMENTS, REFUSED, UNKNOWN_TOOL, Failure, Ok
from harness.tools.native.files import VIEW_IMAGE, view_image_tool
from harness.web.runtime import (
    DEFAULT_TOOLS,
    NOT_CALLABLE_FROM_SCRIPTS,
    SUBAGENT_TOOLS,
    build_runtime,
)
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import (
    CONVERSATION_ID,
    ORIGIN,
    client_tools,
    context_for,
    drain,
    new_session,
    no_approvals,
    no_bots,
    no_progress,
    no_skills,
    runtime_over,
)
from tests.webapp import files_in, images_in, secrets_in

MOST_BYTES = 5 * 1024 * 1024
ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
JPEG_START = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"


async def chunks_of(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def saved_in_the_chat(tmp_path: Path, name: str, data: bytes) -> Path:
    """`data` kept as `name` among the files of the conversation the tests call from."""
    stored = await files_in(tmp_path).save(CONVERSATION_ID, name, chunks_of(data))
    return Path(stored.path)


def viewing(path: Path) -> str:
    return json.dumps({"path": str(path)})


def runtime_seeing(tmp_path: Path, *, vision: bool) -> Runtime:
    return build_runtime(
        Settings(llm={"model": "m", "api_key": "k", "vision": vision}),
        SessionService(JsonlSessionRepository(tmp_path / "sessions")),
        McpService({}),
        no_skills(),
        client_tools(),
        no_approvals(),
        bots=no_bots(SessionService(JsonlSessionRepository(tmp_path / "bot-chats"))),
        subagent_logs=SessionService(JsonlSessionRepository(tmp_path / "subagents")),
        secrets=secrets_in(tmp_path),
        images=images_in(tmp_path),
        files=files_in(tmp_path),
    )


def offered(runtime: Runtime) -> list[str]:
    assert runtime.tools is not None
    return [spec.name for spec in runtime.tools.specs()]


async def test_a_png_in_this_chat_s_folder_comes_back_as_an_image(tmp_path: Path) -> None:
    page = await saved_in_the_chat(tmp_path, "page.png", ONE_PIXEL_PNG)

    shown = await view_image_tool(files_in(tmp_path)).invoke(viewing(page), context=context_for())

    assert isinstance(shown, Ok)
    [image] = shown.images
    assert image.media_type == "image/png"
    assert image.data == page.read_bytes()
    assert str(page) in shown.text


async def test_a_model_that_can_see_reads_the_png_as_an_image_block_in_the_result(
    tmp_path: Path,
) -> None:
    page = await saved_in_the_chat(tmp_path, "page.png", ONE_PIXEL_PNG)
    model = SteppedClient(calls_tool(VIEW_IMAGE, viewing(page)), completed("seen"))
    runtime = runtime_over(model, view_image_tool(files_in(tmp_path)), images=images_in(tmp_path))
    session = new_session()

    await drain(runtime.run("look at the page", session=session, bot_id="b"))

    (result,) = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    assert result.error is None
    assert [block for block in result.message.content if isinstance(block, Image)] == [
        Image(
            media_type="image/png",
            sha256=hashlib.sha256(ONE_PIXEL_PNG).hexdigest(),
            size=len(ONE_PIXEL_PNG),
        )
    ]


async def test_a_jpeg_comes_back_as_a_jpeg(tmp_path: Path) -> None:
    page = await saved_in_the_chat(tmp_path, "page.jpg", JPEG_START)

    shown = await view_image_tool(files_in(tmp_path)).invoke(viewing(page), context=context_for())

    assert isinstance(shown, Ok)
    assert [image.media_type for image in shown.images] == ["image/jpeg"]


async def test_a_path_outside_this_chat_s_folder_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "secret.png"
    outside.write_bytes(ONE_PIXEL_PNG)

    shown = await view_image_tool(files_in(tmp_path)).invoke(
        viewing(outside), context=context_for()
    )

    assert isinstance(shown, Failure)
    assert shown.code == INVALID_ARGUMENTS
    assert "is not a file in this chat" in shown.message


async def test_an_image_over_five_megabytes_is_refused(tmp_path: Path) -> None:
    big = await saved_in_the_chat(tmp_path, "big.png", b"\x89PNG\r\n\x1a\n" + b"\0" * MOST_BYTES)

    shown = await view_image_tool(files_in(tmp_path)).invoke(viewing(big), context=context_for())

    assert isinstance(shown, Failure)
    assert shown.code == INVALID_ARGUMENTS
    assert str(IMAGE_MAX_BYTES) in shown.message


async def test_a_file_that_is_not_a_png_or_jpeg_is_refused_whatever_its_name(
    tmp_path: Path,
) -> None:
    named = await saved_in_the_chat(tmp_path, "page.png", b"GIF89a")

    shown = await view_image_tool(files_in(tmp_path)).invoke(viewing(named), context=context_for())

    assert isinstance(shown, Failure)
    assert shown.message == f"{named} is not a PNG or JPEG image"


def test_the_description_and_the_path_field_are_exactly_the_given_text(tmp_path: Path) -> None:
    spec = view_image_tool(files_in(tmp_path)).spec()

    assert spec.name == VIEW_IMAGE == "view_image"
    assert spec.description == (
        "Shows you an image file kept with this chat, such as a page a skill's script saved: "
        "a JPEG or PNG of at most 5 MB, by its absolute path."
    )
    assert spec.input_schema["properties"]["path"]["description"] == (
        "The image's absolute path, inside this chat's files."
    )
    assert spec.input_schema["required"] == ["path"]


def test_the_main_chat_may_be_offered_it_and_scripts_and_helpers_are_not() -> None:
    assert VIEW_IMAGE in DEFAULT_TOOLS
    assert VIEW_IMAGE in NOT_CALLABLE_FROM_SCRIPTS
    assert VIEW_IMAGE not in SUBAGENT_TOOLS


def test_a_model_that_can_see_is_offered_it(tmp_path: Path) -> None:
    assert VIEW_IMAGE in offered(runtime_seeing(tmp_path, vision=True))


async def test_a_model_that_cannot_see_is_not_offered_it_and_cannot_call_it(
    tmp_path: Path,
) -> None:
    runtime = runtime_seeing(tmp_path, vision=False)
    page = await saved_in_the_chat(tmp_path, "page.png", ONE_PIXEL_PNG)
    call = ToolCall(id="c1", name=VIEW_IMAGE, arguments=viewing(page))

    assert VIEW_IMAGE not in offered(runtime)
    assert runtime.tools is not None
    called = await runtime.tools.execute(call, progress=no_progress, origin=ORIGIN)
    approved = await runtime.tools.execute_approved(call, progress=no_progress, origin=ORIGIN)
    assert isinstance(called, Failure) and called.code == REFUSED
    assert isinstance(approved, Failure) and approved.code == UNKNOWN_TOOL
