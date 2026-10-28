"""A bot's file tools open, unpack and pack only the files of the chat the bot is in."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from harness.config.settings import Settings
from harness.mcp.service import McpService
from harness.session.models import ToolResultEvent
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools.native.files import EXTRACT_ARCHIVE, MAKE_ARCHIVE, VIEW_IMAGE
from harness.web import runtime as composition
from harness.web.runtime import build_runtime
from tests.mcp_stub import DOT_PNG
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import client_tools, drain, no_approvals, no_bots, no_skills
from tests.webapp import files_in, images_in, secrets_with_default_model

DOT = base64.b64decode(DOT_PNG)
NOT_THIS_CHAT = "is not a file in this chat"


async def chunks_of(data: bytes) -> AsyncIterator[bytes]:
    yield data


def zipped_page() -> bytes:
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        archive.writestr("1.png", DOT)
    return packed.getvalue()


async def result_in_chat_s(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool: str, arguments: dict[str, object]
) -> ToolResultEvent:
    """The logged result of one call to `tool` the model makes in chat `s`."""
    model = SteppedClient(calls_tool(tool, json.dumps(arguments)), completed("done"))
    monkeypatch.setattr(composition, "OpenAIClient", lambda _settings, read_image: model)
    sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
    runtime = build_runtime(
        Settings(
            local_settings_path=tmp_path / "config.local.json",
            llm={"model": "m", "api_key": "k", "vision": True},
        ),
        sessions,
        McpService({}),
        no_skills(),
        client_tools(),
        no_approvals(),
        bots=no_bots(SessionService(JsonlSessionRepository(tmp_path / "bot-chats"))),
        subagent_logs=SessionService(JsonlSessionRepository(tmp_path / "subagents")),
        secrets=secrets_with_default_model(tmp_path),
        images=images_in(tmp_path),
        files=files_in(tmp_path),
    )
    session = await sessions.create("s")
    await drain(runtime.run("open it", session=session, bot_id="b"))
    (result,) = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    return result


async def test_view_image_refuses_another_chat_s_image(tmp_path, monkeypatch) -> None:
    theirs = await files_in(tmp_path).save("other", "page.png", chunks_of(DOT))

    result = await result_in_chat_s(tmp_path, monkeypatch, VIEW_IMAGE, {"path": theirs.path})

    assert result.error is not None
    assert NOT_THIS_CHAT in result.message.content[0].text


async def test_extract_archive_refuses_another_chat_s_archive(tmp_path, monkeypatch) -> None:
    theirs = await files_in(tmp_path).save("other", "pages.cbz", chunks_of(zipped_page()))

    result = await result_in_chat_s(tmp_path, monkeypatch, EXTRACT_ARCHIVE, {"path": theirs.path})

    assert result.error is not None
    assert NOT_THIS_CHAT in result.message.content[0].text
    assert not Path(theirs.path).with_name("pages-files").exists()


async def test_make_archive_refuses_another_chat_s_files(tmp_path, monkeypatch) -> None:
    theirs = await files_in(tmp_path).save("other", "page.png", chunks_of(DOT))
    arguments = {"paths": [theirs.path], "name": "out.cbz"}

    result = await result_in_chat_s(tmp_path, monkeypatch, MAKE_ARCHIVE, arguments)

    assert result.error is not None
    assert NOT_THIS_CHAT in result.message.content[0].text
    assert not Path(theirs.path).with_name("out.cbz").exists()
