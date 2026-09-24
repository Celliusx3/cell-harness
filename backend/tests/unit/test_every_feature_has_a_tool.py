"""Every page action that changes something, and every config section, is a tool or says why not."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from harness.config.settings import Settings
from harness.mcp.store import McpServerStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools.native.skills import SKILL_DELETE, SKILL_SAVE
from harness.web.agent import build_agent
from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import client_tools, no_gate, no_skills
from tests.webapp import web_app


class Tool(NamedTuple):
    name: str


class NotATool(NamedTuple):
    reason: str


SECRET = NotATool("a bot token is a secret, and secrets never pass through the model")

ROUTES: dict[str, Tool | NotATool] = {
    "POST /api/conversations": NotATool(
        "starting a conversation is the person's; /new does it from every chat"
    ),
    "POST /api/conversations/{conversation_id}/messages": NotATool(
        "sending is the person's; the model answers in the conversation it is in"
    ),
    "DELETE /api/conversations/{conversation_id}/run": NotATool(
        "stopping is the person's brake; /stop does it from every chat"
    ),
    "POST /api/conversations/{conversation_id}/compact": NotATool(
        "it cannot run during the model's own turn; /compact does it from every chat"
    ),
    "POST /api/conversations/{conversation_id}/calls/{call_id}/output": NotATool(
        "the person's answer to a card; a model that could send it would approve itself"
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
    agent = build_agent(
        Settings(llm={"model": "m", "api_key": "k"}),
        SessionService(JsonlSessionRepository(tmp_path)),
        McpServerStore({}),
        no_skills(),
        client_tools(),
        no_gate(),
    )
    assert agent.tools is not None

    offered = {spec.name for spec in agent.tools.specs()}
    named = {
        entry.name for entry in (*ROUTES.values(), *CONFIG.values()) if isinstance(entry, Tool)
    }

    assert named <= offered
