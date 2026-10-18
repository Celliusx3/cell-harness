"""`extract_archive` and `make_archive`: offered to the main chat as given, never to a script."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.config.settings import Settings
from harness.llm.messages import ToolCall
from harness.mcp.service import McpService
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools.approval import ApprovalGate
from harness.tools.definition import Failure, Ok
from harness.tools.native.code import EXECUTE, LIST
from harness.tools.native.files import (
    EXTRACT_ARCHIVE,
    MAKE_ARCHIVE,
    extract_archive_tool,
    make_archive_tool,
)
from harness.web.runtime import (
    DEFAULT_TOOLS,
    NOT_CALLABLE_FROM_SCRIPTS,
    SUBAGENT_TOOLS,
    build_runtime,
)
from tests.unit.archive_fakes import UNPACK_LIMIT
from tests.unit.helpers import ORIGIN, client_tools, no_bots, no_gate, no_progress, no_skills
from tests.webapp import files_in, images_in, secrets_in

CONFIG = Path(__file__).resolve().parents[2] / "config.json"
ARCHIVE_TOOLS = (EXTRACT_ARCHIVE, MAKE_ARCHIVE)


def test_extract_archive_says_exactly_the_given_text(tmp_path: Path) -> None:
    spec = extract_archive_tool(files_in(tmp_path), UNPACK_LIMIT).spec()

    assert spec.description == (
        "Unpack a .zip or .cbz the person attached into a new folder beside it, so each file "
        "inside can be opened on its own. Returns the paths of the files it wrote, in the "
        "archive's own order, numbered so that 2 comes before 10."
    )
    assert spec.input_schema["properties"]["path"]["description"] == (
        "Absolute path of the .zip or .cbz, a file in the chat files folder."
    )
    assert spec.input_schema["required"] == ["path"]


def test_make_archive_says_exactly_the_given_text(tmp_path: Path) -> None:
    spec = make_archive_tool(files_in(tmp_path)).spec()

    assert spec.description == (
        "Pack files into one new .cbz or .zip beside the first of them, in the order given, such "
        "as the translated pages of a chapter. Returns the path of the archive it wrote; hand it "
        "to the person with send_file."
    )
    assert spec.input_schema["properties"]["paths"]["description"] == (
        "Absolute paths of the files to pack, in order, each in the chat files folder."
    )
    assert spec.input_schema["properties"]["name"]["description"] == (
        "File name of the archive to write, ending in .cbz or .zip, with no folder in it."
    )
    assert spec.input_schema["required"] == ["paths", "name"]


@pytest.mark.parametrize("name", ARCHIVE_TOOLS)
def test_the_main_chat_is_offered_it_and_scripts_and_helpers_are_not(name: str) -> None:
    assert name in DEFAULT_TOOLS
    assert name in NOT_CALLABLE_FROM_SCRIPTS
    assert name not in SUBAGENT_TOOLS


@pytest.mark.parametrize("name", ARCHIVE_TOOLS)
def test_it_never_asks_for_approval(name: str) -> None:
    committed = json.loads(CONFIG.read_text())
    gate = ApprovalGate(
        frozenset(committed["approval"]["tools"]),
        frozenset,
        Path("/nonexistent/cell-harness-approvals.json"),
    )

    assert not gate.asks(name)


async def test_the_runtime_offers_both_and_a_script_can_call_neither(tmp_path: Path) -> None:
    runtime = build_runtime(
        Settings(llm={"model": "m", "api_key": "k"}),
        SessionService(JsonlSessionRepository(tmp_path / "sessions")),
        McpService({}),
        no_skills(),
        client_tools(),
        no_gate(),
        bots=no_bots(SessionService(JsonlSessionRepository(tmp_path / "bot-chats"))),
        subagent_logs=SessionService(JsonlSessionRepository(tmp_path / "subagents")),
        secrets=secrets_in(tmp_path),
        images=images_in(tmp_path),
        files=files_in(tmp_path),
    )
    assert runtime.tools is not None
    offered = [spec.name for spec in runtime.tools.specs()]
    assert EXTRACT_ARCHIVE in offered and MAKE_ARCHIVE in offered

    listed = await runtime.tools.execute(
        ToolCall(id="c1", name=LIST, arguments="{}"), progress=no_progress, origin=ORIGIN
    )
    script = (
        'await extract_archive({path: "/tmp/a.cbz"}); '
        'return await make_archive({paths: ["/tmp/a.png"], name: "a.cbz"});'
    )
    ran = await runtime.tools.execute(
        ToolCall(
            id="c2",
            name=EXECUTE,
            arguments=json.dumps({"code": script, "description": "try"}),
        ),
        progress=no_progress,
        origin=ORIGIN,
    )

    assert isinstance(listed, Ok)
    assert EXTRACT_ARCHIVE not in listed.text and MAKE_ARCHIVE not in listed.text
    assert isinstance(ran, Failure)
    assert "extract_archive is not defined" in ran.message or "cannot be called" in ran.message
