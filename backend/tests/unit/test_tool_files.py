"""Files a tool hands back: read from its result's `_meta`, logged only when they are the chat's."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from mcp.types import CallToolResult, TextContent

from harness.files import ChatFile, ChatFileService, DiskChatFileRepository
from harness.mcp.tool import FILES_META, mcp_tool, outcome_of
from harness.runtime.service import Runtime
from harness.session.log import Session
from harness.session.models import ToolResultEvent
from harness.tools import EXECUTION_ERROR, Failure, Ok
from tests.unit.fakes import OneModel, SteppedClient, calls_tool, completed
from tests.unit.helpers import drain, new_session, toolset_for
from tests.unit.mcp_fakes import tool
from tests.webapp import files_in

PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def result_with(meta: dict[str, object] | None, *, is_error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text="drew it")], _meta=meta, isError=is_error
    )


def ok_of(result: CallToolResult) -> Ok:
    outcome = outcome_of(result, name="srv__draw", server="srv", resource_uri=None)
    assert isinstance(outcome, Ok)
    return outcome


async def chunks_of(body: bytes) -> AsyncIterator[bytes]:
    yield body


async def logged_files(files: ChatFileService | None, meta: dict[str, object]) -> list[ChatFile]:
    """What the log records of a result with `meta`, from an MCP tool called in chat `s`."""

    async def call(name: str, arguments: dict) -> CallToolResult:
        return result_with(meta)

    runtime = Runtime(
        models=OneModel(SteppedClient(calls_tool("srv__draw"), completed("done"))),
        images=None,
        tools=toolset_for(mcp_tool(server="srv", tool=tool("draw"), call=call)),
        files=files,
    )
    session: Session = new_session("s")
    await drain(runtime.run("draw", session=session, bot_id="b"))
    (result,) = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    return list(result.files)


def test_the_paths_under_the_files_key_ride_on_the_outcome() -> None:
    outcome = ok_of(result_with({FILES_META: [{"path": "/a.png"}, {"path": "/b.png"}]}))

    assert outcome.paths_to_send == ("/a.png", "/b.png")
    assert outcome.text == "drew it"


def test_a_result_without_the_files_key_hands_back_nothing() -> None:
    assert ok_of(result_with(None)).paths_to_send == ()
    assert ok_of(result_with({"other": 1})).paths_to_send == ()


def test_a_malformed_entry_is_dropped_and_the_rest_kept(caplog) -> None:
    meta = {FILES_META: [{"path": "/a.png"}, {"url": "/b.png"}, "c.png", {"path": 7}]}

    with caplog.at_level(logging.WARNING, logger="harness.mcp"):
        outcome = ok_of(result_with(meta))

    assert outcome.paths_to_send == ("/a.png",)
    assert len([r for r in caplog.records if "dropped a file" in r.getMessage()]) == 3


def test_a_files_key_that_is_not_a_list_is_dropped(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="harness.mcp"):
        outcome = ok_of(result_with({FILES_META: {"path": "/a.png"}}))

    assert outcome.paths_to_send == ()
    assert "is not a list" in caplog.text


async def test_a_file_in_the_chat_s_folder_is_logged_with_the_result(tmp_path) -> None:
    files = files_in(tmp_path)
    drawn = await files.save("s", "page.png", chunks_of(PNG_HEADER))

    logged = await logged_files(files, {FILES_META: [{"path": drawn.path}]})

    assert logged == [drawn]


async def test_a_file_outside_the_chat_s_folder_is_never_logged(tmp_path, caplog) -> None:
    files = files_in(tmp_path)
    theirs = await files.save("other", "page.png", chunks_of(PNG_HEADER))
    outside = tmp_path / "loose.png"
    outside.write_bytes(PNG_HEADER)
    meta = {FILES_META: [{"path": theirs.path}, {"path": str(outside)}, {"path": "/etc/hosts"}]}

    with caplog.at_level(logging.WARNING, logger="harness.runtime"):
        logged = await logged_files(files, meta)

    assert logged == []
    assert caplog.text.count("dropped") == 3


async def test_a_file_that_does_not_exist_is_never_logged(tmp_path) -> None:
    files = files_in(tmp_path)
    missing = (DiskChatFileRepository(tmp_path / "files").folder("s") / "t" / "gone.png").as_posix()

    assert await logged_files(files, {FILES_META: [{"path": missing}]}) == []


async def test_a_runtime_with_no_chat_files_logs_no_file(tmp_path) -> None:
    files = files_in(tmp_path)
    drawn = await files.save("s", "page.png", chunks_of(PNG_HEADER))

    assert await logged_files(None, {FILES_META: [{"path": drawn.path}]}) == []


def test_a_failed_call_hands_back_no_files() -> None:
    meta = {FILES_META: [{"path": "/a.png"}]}

    outcome = outcome_of(result_with(meta, is_error=True), name="x", server="s", resource_uri=None)

    assert outcome == Failure(EXECUTION_ERROR, "drew it")
