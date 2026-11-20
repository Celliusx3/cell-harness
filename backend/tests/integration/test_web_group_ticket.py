"""A ticket from a group works in its bot's workspace and hands its result over in the group."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from harness.app_events import AppEventService
from harness.bots import ASSISTANT_ID, BotDraft, BotRepository, BotService
from harness.groups import GroupDraft
from harness.session.domain.models import UserMessageEvent
from harness.tickets.domain.prompts import (
    RESULT_FILES_TO_HAND_OVER,
    WORKER_FILES_FOLDER,
    WORKER_OWN_WORKSPACE,
)
from harness.tools import Tool
from harness.tools.domain.context import CallOrigin, ToolContext
from harness.tools.domain.outcome import Ok, ToolOutcome
from harness.tools.native.files.tools import EXTRACT_ARCHIVE
from harness.tools.native.tickets import TICKET_REPORT, TICKET_ROUTE
from tests.integration.ticket_helpers import WORKER_START, ticketing_app
from tests.integration.web_helpers import ASSISTANT_START, of_type, once_said, send
from tests.unit.fakes import EchoArgs, calls_tool, completed, reports_ready
from tests.unit.group_helpers import groups_in
from tests.unit.helpers import durable_service
from tests.webapp import MODEL_CREDENTIAL

RESEARCHER = {"name": "Researcher", "instructions": "RESEARCHER", "model": MODEL_CREDENTIAL}
WRITER = {"name": "Writer", "instructions": "WRITER", "model": MODEL_CREDENTIAL}
ACCEPTED = json.dumps(
    {"items": [{"kind": "accept", "title": "Write hello", "task": "Write hello.txt."}]}
)
HANDED_OVER = "Here is hello.txt."


def _workspace(tmp_path: Path, chat_id: str) -> Path:
    return (tmp_path / "files" / "workspaces" / chat_id).resolve()


async def _group(tmp_path: Path) -> tuple[str, str]:
    """A group of Researcher and then Writer, kept under `tmp_path`; its id and Writer's."""
    sessions = durable_service(tmp_path / "sessions")
    app_events = AppEventService()
    bots = BotService(
        BotRepository(tmp_path / "bots.json"),
        sessions,
        assistant_instructions=ASSISTANT_START,
        app_events=app_events,
    )
    researcher = await bots.create(BotDraft.model_validate(RESEARCHER))
    writer = await bots.create(BotDraft.model_validate(WRITER))
    group = await groups_in(tmp_path, bots, sessions, app_events).create(
        GroupDraft(name="Launch", member_ids=(researcher.id, writer.id))
    )
    return group.id, writer.id


def _shell(hello: Path, origins: list[CallOrigin]) -> Tool[EchoArgs]:
    """A worker tool standing in for the PC's shell: it keeps its origin and writes `hello`."""

    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        origins.append(context.origin)
        hello.parent.mkdir(parents=True, exist_ok=True)
        hello.write_text(args.value)
        return Ok("written")

    return Tool.from_model(
        name=EXTRACT_ARCHIVE, description="Run it.", args_model=EchoArgs, execute=execute
    )


async def test_a_ticket_from_a_group_works_in_its_bots_workspace_and_reports_in_the_group(
    tmp_path,
) -> None:
    group, writer = await _group(tmp_path)
    group_workspace, own_workspace = _workspace(tmp_path, group), _workspace(tmp_path, writer)
    hello = group_workspace / "hello.txt"
    origins: list[CallOrigin] = []
    ready = json.dumps({"state": "ready", "summary": f"Wrote {hello}"})
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [
                calls_tool(EXTRACT_ARCHIVE, json.dumps({"value": "hello"}), id="s1"),
                calls_tool(TICKET_REPORT, ready, id="r1"),
                completed("Reported."),
            ],
            WRITER["instructions"]: [
                calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
                completed("On it."),
                completed(HANDED_OVER),
            ],
            RESEARCHER["instructions"]: [completed("Not mine to answer.")],
        },
        bot_tools=lambda bots, secrets: (_shell(hello, origins),),
    )
    async with world.client as client:
        await send(client, group, "@Writer write hello.txt for me")
        log = await once_said(client, group, HANDED_OVER)
        (ticket,) = world.tickets.of_bot(writer)
        served = await client.get(f"/api/tickets/{ticket.id}/file", params={"path": str(hello)})
        own_log = (await client.get(f"/api/conversations/{writer}")).json()["events"]

    assert ticket.chat_id == group
    assert [origin.workspace for origin in origins] == [own_workspace]
    first = next(
        e for e in await world.tickets.worker_events(ticket.id) if isinstance(e, UserMessageEvent)
    )
    folder_line = WORKER_FILES_FOLDER.format(folder=group_workspace)
    own_line = WORKER_OWN_WORKSPACE.format(workspace=own_workspace)
    assert f"{folder_line}\n\n{own_line}" in first.message.content
    assert [e["bot_id"] for e in of_type(log, "turn/start")] == [writer, writer]
    assert world.model.seen_by[RESEARCHER["instructions"]] == []
    (report,) = of_type(log, "ticket/report")
    assert RESULT_FILES_TO_HAND_OVER.format(paths=hello) in report["report"]["text"]
    assert of_type(own_log, "ticket/report") == []
    assert served.status_code == 200
    assert served.content == b"hello"


def _queued(tmp_path: Path, **chat: str) -> None:
    """A queued ticket of Assistant's in the tickets file, with `chat` as it was kept."""
    stored = {
        "id": "t1",
        "bot_id": ASSISTANT_ID,
        "title": "Write hello",
        "task": "Write hello.txt.",
        "state": "queued",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        **chat,
    }
    (tmp_path / "tickets.json").write_text(json.dumps({"tickets": [stored]}))


def _assistant_world(tmp_path: Path):
    return ticketing_app(
        tmp_path,
        {
            WORKER_START: [reports_ready("Wrote it.")],
            ASSISTANT_START: [completed("Here it is.")],
        },
    )


async def test_a_ticket_stored_before_chats_were_kept_reports_in_its_bots_chat(tmp_path) -> None:
    _queued(tmp_path)
    world = _assistant_world(tmp_path)
    async with world.client as client:
        world.tickets.recover()
        log = await once_said(client, ASSISTANT_ID, "Here it is.")

    (report,) = of_type(log, "ticket/report")
    assert report["report"]["ticket_id"] == "t1"
    first = next(
        e for e in await world.tickets.worker_events("t1") if isinstance(e, UserMessageEvent)
    )
    workspace = _workspace(tmp_path, ASSISTANT_ID)
    assert WORKER_FILES_FOLDER.format(folder=workspace) in first.message.content
    assert "Your shell starts in your bot's workspace" not in first.message.content


async def test_a_report_from_a_group_its_bot_no_longer_answers_in_goes_to_its_own_chat(
    tmp_path,
) -> None:
    group, _ = await _group(tmp_path)
    _queued(tmp_path, chat_id=group)
    world = _assistant_world(tmp_path)
    async with world.client as client:
        world.tickets.recover()
        log = await once_said(client, ASSISTANT_ID, "Here it is.")
        group_log = (await client.get(f"/api/conversations/{group}")).json()["events"]

    assert [r["report"]["ticket_id"] for r in of_type(log, "ticket/report")] == ["t1"]
    assert of_type(group_log, "ticket/report") == []
