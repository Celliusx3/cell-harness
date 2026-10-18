"""The runtime and images: what it keeps of an attachment, and when no image may be sent at all."""

from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path

from harness.files import ChatFile
from harness.images import IMAGE_MAX_BYTES, ImageService
from harness.llm.messages import Image, Message, UserMessage, images_of
from harness.prompts import ATTACHED_FILE, IMAGE_NOT_SHOWN
from harness.runtime.compaction import run_compaction
from harness.session.models import UserMessageEvent
from tests.mcp_stub import DOT_PNG
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import drain, new_session, runtime_over
from tests.unit.test_derive_images import person_then_tool
from tests.unit.test_image_service import images_at

DOT = base64.b64decode(DOT_PNG)
DOT_IMAGE = Image(media_type="image/png", sha256=hashlib.sha256(DOT).hexdigest(), size=len(DOT))


def attached(path: Path, *, media_type: str = "image/png", size: int | None = None) -> ChatFile:
    """`path` as the web route records an attachment, its size read from disk unless given."""
    return ChatFile(
        path=str(path),
        name=path.name,
        media_type=media_type,
        size=path.stat().st_size if size is None else size,
    )


async def person_s_message(images: ImageService | None, files: tuple[ChatFile, ...]) -> UserMessage:
    """The person's message as logged, once a turn opened with `files` attached."""
    runtime = runtime_over(ScriptedClient(completed("seen")), images=images)
    session = new_session()
    await drain(runtime.run("look", session=session, bot_id="b", files=files))
    (event,) = [e for e in session.events() if isinstance(e, UserMessageEvent)]
    return event.message


def shown(messages: list[Message]) -> list[Image]:
    return [image for message in messages for image in images_of(message)]


async def test_an_attached_image_is_kept_and_rides_the_person_s_message(tmp_path) -> None:
    (tmp_path / "page.png").write_bytes(DOT)
    images = images_at(tmp_path / "blobs")

    message = await person_s_message(images, (attached(tmp_path / "page.png"),))

    assert message.images == (DOT_IMAGE,)
    assert images.read(DOT_IMAGE) == DOT


async def test_without_vision_an_attached_image_is_only_its_line(tmp_path) -> None:
    (tmp_path / "page.png").write_bytes(DOT)
    page = attached(tmp_path / "page.png")
    model = ScriptedClient(completed("seen"))
    runtime = runtime_over(model, images=None)

    await drain(runtime.run("look", session=new_session(), bot_id="b", files=(page,)))

    line = ATTACHED_FILE.format(
        name="page.png", media_type="image/png", size=len(DOT), path=page.path
    )
    assert model.seen == [UserMessage(content=f"look\n\n{line}")]


async def test_an_attached_image_over_five_megabytes_is_not_shown(tmp_path) -> None:
    (tmp_path / "huge.png").write_bytes(DOT)
    huge = attached(tmp_path / "huge.png", size=IMAGE_MAX_BYTES + 1)

    message = await person_s_message(images_at(tmp_path / "blobs"), (huge,))

    assert message.images == ()
    assert not (tmp_path / "blobs").exists()


async def test_an_attached_file_that_is_not_an_image_is_left_to_its_line(tmp_path) -> None:
    (tmp_path / "notes.txt").write_text("hi")
    notes = attached(tmp_path / "notes.txt", media_type="text/plain")

    message = await person_s_message(images_at(tmp_path / "blobs"), (notes,))

    assert message.images == ()


async def test_an_attached_image_that_cannot_be_read_is_left_to_its_line(tmp_path, caplog) -> None:
    gone = ChatFile(
        path=str(tmp_path / "gone.png"), name="gone.png", media_type="image/png", size=8
    )

    with caplog.at_level(logging.WARNING, logger="harness.images"):
        message = await person_s_message(images_at(tmp_path / "blobs"), (gone,))

    assert message.images == ()
    assert "gone.png is not shown" in caplog.text


async def test_an_image_that_cannot_be_kept_is_not_shown(tmp_path, caplog) -> None:
    (tmp_path / "page.png").write_bytes(DOT)
    (tmp_path / "blobs").write_text("a file where the folder should be")

    with caplog.at_level(logging.WARNING, logger="harness.images"):
        message = await person_s_message(
            images_at(tmp_path / "blobs"), (attached(tmp_path / "page.png"),)
        )

    assert message.images == ()
    assert "could not be kept" in caplog.text


def test_without_vision_an_image_already_logged_is_not_sent() -> None:
    session = new_session()
    for event in person_then_tool(attached=(DOT_IMAGE,), returned=()):
        session.append(event)

    messages = runtime_over(ScriptedClient([]), images=None).request_messages(session)

    assert shown(messages) == []
    assert messages[0] == UserMessage(content=f"look\n{IMAGE_NOT_SHOWN}")


async def test_the_summary_request_carries_no_images(tmp_path) -> None:
    session = new_session()
    for event in person_then_tool(attached=(DOT_IMAGE,), returned=(DOT_IMAGE,)):
        session.append(event)
    client = ScriptedClient(completed("THE SUMMARY"))
    runtime = runtime_over(client, images=images_at(tmp_path))
    assert len(shown(runtime.request_messages(session))) == 2

    await drain(run_compaction(runtime, session, turn=1, trigger="manual"))

    assert client.calls == 1
    assert shown(client.seen) == []
    assert client.seen[0] == UserMessage(content=f"look\n{IMAGE_NOT_SHOWN}")
