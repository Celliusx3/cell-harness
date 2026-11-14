"""The file tools open, unpack and pack only the files of the chat they are called in."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from harness.bots import ASSISTANT_ID
from harness.config.settings import Settings
from harness.mcp import McpService
from harness.session.domain.models import ToolResultEvent
from harness.session.repository.jsonl_session_repository import JsonlSessionRepository
from harness.session.service.session_service import SessionService
from harness.tickets.service.worker import worker_session_id
from harness.tools.native.files import EXTRACT_ARCHIVE, MAKE_ARCHIVE, VIEW_IMAGE
from harness.web import runtime as composition
from harness.web.runtime import build_runtime
from harness.web.tickets_wiring import ticket_workers
from tests.bot_models import assistant_on_a_model
from tests.mcp_stub import DOT_PNG
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import client_tools, drain, no_approvals, no_skills
from tests.webapp import bots_in, files_in, images_in

DOT = base64.b64decode(DOT_PNG)
NOT_THIS_CHAT = "is not a file in this chat"


async def chunks_of(data: bytes) -> AsyncIterator[bytes]:
    yield data


def zipped_page() -> bytes:
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        archive.writestr("1.png", DOT)
    return packed.getvalue()


async def worker_call_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
    arguments: dict[str, object],
    session_id: str = "s",
) -> ToolResultEvent:
    """The logged result of one call to `tool` a worker makes in `session_id`, offered them all."""
    model = SteppedClient(calls_tool(tool, json.dumps(arguments)), completed("done"))
    monkeypatch.setattr(composition, "OpenAIClient", lambda _settings, read_image: model)
    sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
    bots = bots_in(tmp_path, SessionService(JsonlSessionRepository(tmp_path / "bot-chats")))
    logs = SessionService(JsonlSessionRepository(tmp_path / "subagents"))
    bot = build_runtime(
        Settings(),
        sessions,
        McpService({}),
        no_skills(),
        client_tools(),
        no_approvals(),
        bots=bots,
        subagent_logs=logs,
        secrets=assistant_on_a_model(tmp_path, bots),
        images=images_in(tmp_path),
        files=files_in(tmp_path),
    )
    assert bot.tools is not None
    runtime = ticket_workers(bot.tools.tool_service, bot, logs, bots.chat_of).runtime
    session = await sessions.create(session_id)
    await drain(runtime.run("open it", session=session, bot_id=ASSISTANT_ID))
    (result,) = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    return result


async def test_view_image_refuses_another_chat_s_image(tmp_path, monkeypatch) -> None:
    theirs = await files_in(tmp_path).save("other", "page.png", chunks_of(DOT))

    result = await worker_call_result(tmp_path, monkeypatch, VIEW_IMAGE, {"path": theirs.path})

    assert result.error is not None
    assert NOT_THIS_CHAT in result.message.content[0].text


async def test_a_worker_opens_an_image_in_its_bots_chat(tmp_path, monkeypatch) -> None:
    page = await files_in(tmp_path).save(ASSISTANT_ID, "page.png", chunks_of(DOT))

    result = await worker_call_result(
        tmp_path, monkeypatch, VIEW_IMAGE, {"path": page.path}, worker_session_id("t1")
    )

    assert result.error is None


async def test_extract_archive_refuses_another_chat_s_archive(tmp_path, monkeypatch) -> None:
    theirs = await files_in(tmp_path).save("other", "pages.cbz", chunks_of(zipped_page()))

    result = await worker_call_result(tmp_path, monkeypatch, EXTRACT_ARCHIVE, {"path": theirs.path})

    assert result.error is not None
    assert NOT_THIS_CHAT in result.message.content[0].text
    assert not Path(theirs.path).with_name("pages-files").exists()


async def test_make_archive_refuses_another_chat_s_files(tmp_path, monkeypatch) -> None:
    theirs = await files_in(tmp_path).save("other", "page.png", chunks_of(DOT))
    arguments = {"paths": [theirs.path], "name": "out.cbz"}

    result = await worker_call_result(tmp_path, monkeypatch, MAKE_ARCHIVE, arguments)

    assert result.error is not None
    assert NOT_THIS_CHAT in result.message.content[0].text
    assert not Path(theirs.path).with_name("out.cbz").exists()
