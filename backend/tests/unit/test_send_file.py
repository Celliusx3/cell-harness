"""`send_file`: files in this chat's folder reach the person, and the model hears which did not."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

from pydantic import BaseModel

from harness.config.settings import Settings
from harness.files import ChatFileService, DiskChatFileRepository
from harness.llm import ToolCall, ToolMessage, text_of
from harness.mcp.service import McpService
from harness.prompts import HANDED_OVER, NOT_HANDED_OVER
from harness.runtime.service import Runtime
from harness.session.log import Session
from harness.session.models import ToolResultEvent
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools import (
    INVALID_ARGUMENTS,
    ApprovalService,
    Failure,
    Ok,
    Tool,
    ToolContext,
    ToolOutcome,
)
from harness.tools.native.code_mode import EXECUTE_TYPESCRIPT, LIST_FUNCTIONS
from harness.tools.native.files import SEND_FILE, send_file_tool
from harness.web.runtime import (
    DEFAULT_TOOLS,
    NOT_CALLABLE_FROM_SCRIPTS,
    SUBAGENT_TOOLS,
    build_runtime,
)
from tests.unit.fakes import OneModel, SteppedClient, calls_tool, completed
from tests.unit.helpers import (
    ORIGIN,
    client_tools,
    context_for,
    drain,
    new_session,
    no_approvals,
    no_bots,
    no_progress,
    no_skills,
    toolset_for,
)
from tests.webapp import files_in, images_in, secrets_in

CONFIG = Path(__file__).resolve().parents[2] / "config.json"
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


class NoArgs(BaseModel):
    """A fake tool's arguments: none."""


async def chunks_of(body: bytes) -> AsyncIterator[bytes]:
    yield body


async def session_after(tool: Tool, files: ChatFileService, arguments: str) -> Session:
    """Chat `s` after the model calls `tool` once with `arguments` and then answers."""
    runtime = Runtime(
        models=OneModel(SteppedClient(calls_tool(tool.name, arguments), completed("done"))),
        images=None,
        tools=toolset_for(tool),
        files=files,
    )
    session = new_session("s")
    await drain(runtime.run("hand it over", session=session, bot_id="b"))
    return session


def the_result(session: Session) -> ToolResultEvent:
    (result,) = [event for event in session.events() if isinstance(event, ToolResultEvent)]
    return result


def what_the_model_reads(session: Session) -> str:
    runtime = Runtime(models=OneModel(SteppedClient()), images=None)
    (message,) = [m for m in runtime.request_messages(session) if isinstance(m, ToolMessage)]
    return text_of(message.content)


def sending(*paths: str) -> str:
    return json.dumps({"paths": list(paths)})


async def test_a_file_in_this_chat_s_folder_is_logged_on_the_result_as_a_stored_file(
    tmp_path: Path,
) -> None:
    files = files_in(tmp_path)
    page = await files.save("s", "page-english.png", chunks_of(PNG_HEADER))

    session = await session_after(send_file_tool(), files, sending(page.path))

    assert the_result(session).files == (page,)
    assert the_result(session).error is None
    assert what_the_model_reads(session) == HANDED_OVER.format(path=page.path)


async def test_a_path_outside_this_chat_s_folder_is_not_handed_over_and_the_model_is_told(
    tmp_path: Path,
) -> None:
    files = files_in(tmp_path)
    theirs = await files.save("other", "page.png", chunks_of(PNG_HEADER))
    missing = str(DiskChatFileRepository(tmp_path / "files").folder("s") / "t" / "gone.png")
    refused = (theirs.path, "/etc/hosts", missing)

    session = await session_after(send_file_tool(), files, sending(*refused))

    assert the_result(session).files == ()
    assert what_the_model_reads(session) == "\n".join(
        NOT_HANDED_OVER.format(path=path) for path in refused
    )


async def test_of_several_paths_only_the_ones_in_this_chat_s_folder_are_handed_over(
    tmp_path: Path,
) -> None:
    files = files_in(tmp_path)
    page = await files.save("s", "page.png", chunks_of(PNG_HEADER))
    layered = await files.save("s", "page.psd", chunks_of(b"8BPS"))

    session = await session_after(
        send_file_tool(), files, sending(page.path, "/etc/hosts", layered.path)
    )

    assert the_result(session).files == (page, layered)
    assert what_the_model_reads(session).splitlines() == [
        HANDED_OVER.format(path=page.path),
        NOT_HANDED_OVER.format(path="/etc/hosts"),
        HANDED_OVER.format(path=layered.path),
    ]


async def test_any_tool_s_refused_path_is_named_after_its_own_words(tmp_path: Path) -> None:
    files = files_in(tmp_path)
    drawn = await files.save("s", "drawn.png", chunks_of(PNG_HEADER))

    async def execute(_args: NoArgs, _context: ToolContext) -> ToolOutcome:
        return Ok("drew it", paths_to_send=(drawn.path, "/etc/hosts"))

    draw = Tool.from_model(name="draw", description="Draw.", args_model=NoArgs, execute=execute)

    session = await session_after(draw, files, "{}")

    assert the_result(session).files == (drawn,)
    assert what_the_model_reads(session) == (
        "drew it\n\n"
        f"{HANDED_OVER.format(path=drawn.path)}\n{NOT_HANDED_OVER.format(path='/etc/hosts')}"
    )


async def test_a_result_that_names_no_file_reads_as_its_own_words_alone(tmp_path: Path) -> None:
    async def execute(_args: NoArgs, _context: ToolContext) -> ToolOutcome:
        return Ok("nothing drawn")

    plain = Tool.from_model(name="plain", description="Plain.", args_model=NoArgs, execute=execute)

    session = await session_after(plain, files_in(tmp_path), "{}")

    assert what_the_model_reads(session) == "nothing drawn"


async def test_asking_to_hand_over_no_path_is_invalid_arguments() -> None:
    outcome = await send_file_tool().invoke(sending(), context=context_for())

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS


def test_the_description_and_the_paths_field_are_exactly_the_given_text() -> None:
    spec = send_file_tool().spec()

    assert spec.description == (
        "Hand the person files from this chat's folder, such as a page a tool saved next to a "
        "file they attached. Each file appears under this call: a picture as a thumbnail they "
        "can open full size, anything else as a download. Returns the paths handed over, and "
        "each path that was not, because it is not a file in this chat's folder."
    )
    assert spec.input_schema["properties"]["paths"]["description"] == (
        "Absolute paths of the files to hand over, each a file inside this chat's folder."
    )
    assert spec.input_schema["required"] == ["paths"]


def test_the_main_chat_is_offered_it_and_scripts_and_helpers_are_not() -> None:
    assert SEND_FILE in DEFAULT_TOOLS
    assert SEND_FILE in NOT_CALLABLE_FROM_SCRIPTS
    assert SEND_FILE not in SUBAGENT_TOOLS


def test_it_never_asks_for_approval() -> None:
    committed = json.loads(CONFIG.read_text())
    approvals = ApprovalService(
        frozenset(committed["approval"]["tools"]),
        frozenset,
        Path("/nonexistent/cell-harness-approvals.json"),
    )

    assert not approvals.needs_approval(SEND_FILE)


async def test_a_script_cannot_hand_over_a_file(tmp_path: Path) -> None:
    runtime = build_runtime(
        Settings(
            local_settings_path=tmp_path / "config.local.json", llm={"model": "m", "api_key": "k"}
        ),
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
    assert runtime.tools is not None
    assert SEND_FILE in [spec.name for spec in runtime.tools.specs()]

    listed = await runtime.tools.execute(
        ToolCall(id="c1", name=LIST_FUNCTIONS, arguments="{}"),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
    )
    ran = await runtime.tools.execute(
        ToolCall(
            id="c2",
            name=EXECUTE_TYPESCRIPT,
            arguments=json.dumps(
                {"code": 'return await send_file({paths: ["/etc/hosts"]});', "description": "try"}
            ),
        ),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
    )

    assert isinstance(listed, Ok) and SEND_FILE not in listed.text
    assert isinstance(ran, Failure)
    assert "send_file is not defined" in ran.message or "cannot be called" in ran.message
