"""Every page action that changes something, and every config section, is a tool or says why not."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from harness.bots import MENTION_TURN_ORDER, GroupService
from harness.config.settings import Settings
from harness.mcp import McpService
from harness.session.repository.jsonl_session_repository import JsonlSessionRepository
from harness.session.service.session_service import SessionService
from harness.tools.native.bots import BOT_CREATE
from harness.tools.native.schedule import SCHEDULE_EDIT
from harness.tools.native.skills import SKILL_DELETE, SKILL_SAVE
from harness.web.runtime import attach_schedules, build_runtime
from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import client_tools, no_approvals, no_bots, no_skills
from tests.webapp import a_model_saved_in, files_in, images_in, schedules_in, web_app


class Tool(NamedTuple):
    name: str


class NotATool(NamedTuple):
    reason: str


ROUTES: dict[str, Tool | NotATool] = {
    "POST /api/conversations/{conversation_id}/messages": NotATool(
        "sending is the person's; the model answers in the conversation it is in"
    ),
    "DELETE /api/conversations/{conversation_id}/run": NotATool(
        "stopping is the person's brake; /stop does it from every chat"
    ),
    "POST /api/conversations/{conversation_id}/compact": NotATool(
        "it cannot run during the model's own turn; /compact does it from every chat"
    ),
    "POST /api/conversations/{conversation_id}/clear": NotATool(
        "a clear stops the turn in flight, the model's own; /new does it from every chat"
    ),
    "PUT /api/conversations/{conversation_id}/mode": NotATool(
        "what asks in a chat is the person's call; a model that switched it would approve itself"
    ),
    "POST /api/conversations/{conversation_id}/calls/{call_id}/output": NotATool(
        "the person's answer to a card; a model that could send it would approve itself"
    ),
    "POST /api/conversations/{conversation_id}/calls/{call_id}/secret": NotATool(
        "the person types the key on the card; it never passes the model"
    ),
    "POST /api/conversations/{conversation_id}/files": NotATool(
        "the bytes are on the person's device; a tool hands its own files back in its result"
    ),
    "POST /api/skills": NotATool(
        "a zip is bytes the model does not have; skill_save and skill_write_file write its files"
    ),
    "PUT /api/skills/{name}": Tool(SKILL_SAVE),
    "DELETE /api/skills/{name}": Tool(SKILL_DELETE),
    "DELETE /api/approvals/{tool}": NotATool(
        "not yet: taking back an 'Always allow' from chat is the next piece"
    ),
    "POST /api/mcp/{server}/tools/{name}": NotATool(
        "an MCP App's own call to its server; the model reaches that tool through code mode"
    ),
    "OPTIONS /api/mcp/servers": NotATool("a browser's preflight; it changes nothing"),
    "OPTIONS /api/mcp/servers/{server_id}": NotATool("a browser's preflight; it changes nothing"),
    "OPTIONS /api/mcp/servers/{server_id}/restart": NotATool(
        "a browser's preflight; it changes nothing"
    ),
    "POST /api/mcp/servers": NotATool(
        "a server is a program run on the person's Mac; only the person adds one, on the screen"
    ),
    "PUT /api/mcp/servers/{server_id}": NotATool(
        "changing the program a server runs is the person's call, on the MCP servers screen"
    ),
    "DELETE /api/mcp/servers/{server_id}": NotATool(
        "removing a server is the person's call, on the MCP servers screen"
    ),
    "POST /api/mcp/servers/{server_id}/restart": NotATool(
        "not yet: restarting a failed server from chat; the person does it on the screen"
    ),
    "POST /api/bots": Tool(BOT_CREATE),
    "PUT /api/bots/{bot_id}": NotATool(
        "not yet: a bot made from chat has its instructions changed on its page"
    ),
    "POST /api/bots/{bot_id}/archive": NotATool(
        "hiding a teammate the person made is the person's call, from its page"
    ),
    "POST /api/bots/{bot_id}/restore": NotATool(
        "bringing a teammate back from the archive is the person's call, from the sidebar"
    ),
    "DELETE /api/bots/{bot_id}": NotATool(
        "it erases a teammate and its chat for good; only the person does that"
    ),
    "POST /api/schedules/{schedule_id}/pause": Tool(SCHEDULE_EDIT),
    "POST /api/schedules/{schedule_id}/resume": Tool(SCHEDULE_EDIT),
    "DELETE /api/schedules/{schedule_id}": Tool(SCHEDULE_EDIT),
    "POST /api/schedules/{schedule_id}/run": NotATool(
        "a bot already doing the task does it at once; running one early is the person's call"
    ),
    "POST /api/tickets/{ticket_id}/answer": NotATool(
        "the person's answer to a worker's question; ticket_note sends the bot's own facts"
    ),
    "POST /api/tickets/{ticket_id}/approve": NotATool(
        "allowing a worker's call is the person's call, as on the bot's own approval card"
    ),
    "POST /api/tickets/{ticket_id}/secret": NotATool(
        "the key the person pastes for a worker's question; no model ever sees a key"
    ),
    "POST /api/tickets/{ticket_id}/stop": NotATool(
        "stopping from Needs you is the person's call; ticket_route's stop is the bot's own"
    ),
    "POST /api/tickets/{ticket_id}/retry": NotATool(
        "trying again from Needs you is the person's call; ticket_route attaches the bot's own"
    ),
    "POST /api/groups": NotATool("not yet: making a group from chat is the next piece"),
    "PUT /api/bots/{bot_id}/secrets": NotATool(
        "which keys a bot may use is the person's call; a bot never gives itself a key"
    ),
    "POST /api/bots/{bot_id}/link-codes": NotATool(
        "a code lets someone's chat talk to a bot; only the person hands one out, from its page"
    ),
    "OPTIONS /api/credentials": NotATool("a browser's preflight; it changes nothing"),
    "OPTIONS /api/credentials/{name}": NotATool("a browser's preflight; it changes nothing"),
    "POST /api/credentials": NotATool(
        "the person types the key on the Mac that runs the harness; it never passes the model"
    ),
    "PATCH /api/credentials/{name}": NotATool(
        "a new key or new bots for a credential is the person's call; a bot never gives itself one"
    ),
    "DELETE /api/credentials/{name}": NotATool(
        "removing a key is the person's call, from the Credentials page"
    ),
}

CONFIG: dict[str, Tool | NotATool] = {
    "llm": NotATool("how every model is asked; a bot's own model is picked in Edit bot"),
    "sessions": NotATool("where conversations are stored; moving it while running loses them"),
    "web": NotATool("the address the app is reached at belongs to whoever hosts it"),
    "code": NotATool("the sandbox's limits; the model never loosens its own"),
    "compaction": NotATool("the model's window size, set once per model"),
    "mcp": NotATool(
        "the servers config builds in, and where the person's own are kept; set at start"
    ),
    "skills": NotATool("where skills live; skill_save and skill_delete work in the editable one"),
    "approval": NotATool("what the model must ask before doing; it never edits its own list"),
    "bots": NotATool("where the bots are kept; moving it while running loses them"),
    "schedules": NotATool("where the schedules are kept; moving it while running loses them"),
    "tickets": NotATool("where the tickets are kept; moving it while running loses them"),
    "secrets": NotATool(
        "where keys are kept and the key that locks them; neither ever passes the model"
    ),
    "files": NotATool("where each chat's files are kept and the upload limit; the person's"),
}


def test_every_page_action_that_changes_something_names_its_tool_or_a_reason(
    tmp_path: Path,
) -> None:
    service, runs = build(tmp_path, ScriptedClient(completed("hi")))
    app = web_app(tmp_path, service, runs, skills=no_skills())

    changing = {
        f"{method.upper()} {path}"
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method != "get"
    }

    assert changing == set(ROUTES)


def test_every_config_section_names_its_tool_or_a_reason() -> None:
    assert set(Settings.model_fields) == set(CONFIG)


def test_every_tool_the_tables_name_is_offered_to_the_model(tmp_path: Path) -> None:
    bot_chats = SessionService(JsonlSessionRepository(tmp_path / "bot-chats"))
    bots = no_bots(bot_chats)
    runtime = build_runtime(
        Settings(),
        SessionService(JsonlSessionRepository(tmp_path)),
        McpService({}),
        no_skills(),
        client_tools(),
        no_approvals(),
        bots=bots,
        subagent_logs=SessionService(JsonlSessionRepository(tmp_path / "subagents")),
        secrets=a_model_saved_in(tmp_path),
        images=images_in(tmp_path),
        files=files_in(tmp_path),
    )
    assert runtime.tools is not None
    attach_schedules(
        runtime.tools.tool_service,
        GroupService(bots, bot_chats, MENTION_TURN_ORDER),
        schedules_in(tmp_path),
    )

    offered = {spec.name for spec in runtime.tools.specs(sees_images=False)}
    named = {
        entry.name for entry in (*ROUTES.values(), *CONFIG.values()) if isinstance(entry, Tool)
    }

    assert named <= offered
