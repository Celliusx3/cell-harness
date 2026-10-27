"""Every page action that changes something, and every config section, is a tool or says why not."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from harness.config.settings import Settings
from harness.mcp.service import McpService
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools.native.bots import BOT_CREATE
from harness.tools.native.skills import SKILL_DELETE, SKILL_SAVE
from harness.web.runtime import build_runtime
from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import client_tools, no_approvals, no_bots, no_skills
from tests.webapp import files_in, images_in, secrets_in, web_app


class Tool(NamedTuple):
    name: str


class NotATool(NamedTuple):
    reason: str


SECRET = NotATool("a bot token is a secret, and secrets never pass through the model")

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
    "POST /api/groups": NotATool("not yet: making a group from chat is the next piece"),
    "PUT /api/bots/{bot_id}/secrets": NotATool(
        "which keys a bot may use is the person's call; a bot never gives itself a key"
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
    "llm": NotATool("not yet: switching model from chat; the api key never passes the model"),
    "sessions": NotATool("where conversations are stored; moving it while running loses them"),
    "telegram": SECRET,
    "discord": SECRET,
    "web": NotATool("the address the app is reached at belongs to whoever hosts it"),
    "code": NotATool("the sandbox's limits; the model never loosens its own"),
    "compaction": NotATool("the model's window size, set once per model"),
    "mcp": NotATool("not yet: connecting from chat needs a server to start while the app runs"),
    "skills": NotATool("where skills live; skill_save and skill_delete work in the editable one"),
    "approval": NotATool("what the model must ask before doing; it never edits its own list"),
    "bots": NotATool("where the bots are kept; moving it while running loses them"),
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
    runtime = build_runtime(
        Settings(llm={"model": "m", "api_key": "k"}),
        SessionService(JsonlSessionRepository(tmp_path)),
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

    offered = {spec.name for spec in runtime.tools.specs()}
    named = {
        entry.name for entry in (*ROUTES.values(), *CONFIG.values()) if isinstance(entry, Tool)
    }

    assert named <= offered
