"""Skills through the real object graph: offered while one exists, withheld from scripts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.agent.loop import LoopAgent
from harness.config.sections import McpServer
from harness.config.settings import Settings
from harness.llm.messages import ToolCall
from harness.mcp.store import McpServerStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import SKILL
from harness.tools.definition import Ok
from harness.tools.native.code import EXECUTE, LIST
from harness.web.agent import DEFAULT_TOOLS, build_agent
from tests.unit.helpers import client_tools, no_progress, skills_at


def write_skill(root: Path, name: str) -> Path:
    (root / name).mkdir(parents=True)
    (root / name / "SKILL.md").write_text(f"---\ndescription: {name} things.\n---\nDo {name}.\n")
    return root / name


@pytest.fixture
def compose(tmp_path: Path):
    root = tmp_path / "skills"
    root.mkdir()

    def build() -> LoopAgent:
        settings = Settings(llm={"model": "m", "api_key": "k"})
        sessions = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
        mcp = McpServerStore({"stub": McpServer(command="does-not-run")})
        return build_agent(settings, sessions, mcp, skills_at(root), client_tools())

    return build, root


def test_the_tool_is_offered_exactly_while_a_skill_exists(compose) -> None:
    build, root = compose
    agent = build()
    assert agent.tools is not None

    assert SKILL not in [s.name for s in agent.tools.specs()]

    directory = write_skill(root, "pdf")
    offered = [s.name for s in agent.tools.specs()]
    assert SKILL in offered
    assert offered == list(DEFAULT_TOOLS)

    (directory / "SKILL.md").unlink()
    assert SKILL not in [s.name for s in agent.tools.specs()]


async def test_the_tool_dispatches_and_returns_the_body(compose) -> None:
    build, root = compose
    write_skill(root, "pdf")
    agent = build()
    assert agent.tools is not None

    outcome = await agent.tools.execute(
        ToolCall(id="c1", name=SKILL, arguments=json.dumps({"name": "pdf"})), progress=no_progress
    )

    assert isinstance(outcome, Ok) and "Do pdf." in outcome.text


async def test_a_script_cannot_reach_it(compose) -> None:
    build, root = compose
    write_skill(root, "pdf")
    agent = build()
    assert agent.tools is not None

    listed = await agent.tools.execute(
        ToolCall(id="c1", name=LIST, arguments="{}"), progress=no_progress
    )
    assert isinstance(listed, Ok) and "skill" not in listed.text

    ran = await agent.tools.execute(
        ToolCall(
            id="c2",
            name=EXECUTE,
            arguments=json.dumps(
                {"code": 'return await skill({name: "pdf"});', "description": "try"}
            ),
        ),
        progress=no_progress,
    )
    assert "skill is not defined" in str(ran).lower() or "cannot be called" in str(ran)


def test_a_skill_saved_through_the_editor_is_offered_next_request(compose) -> None:
    build, root = compose
    agent = build()
    assert agent.tools is not None
    assert SKILL not in [s.name for s in agent.tools.specs()]

    skills_at(root).save("notes", "---\ndescription: Notes.\n---\nWrite them.\n")

    (spec,) = [s for s in agent.tools.specs() if s.name == SKILL]
    assert spec.input_schema["properties"]["name"]["enum"] == ["notes"]

    skills_at(root).delete("notes")
    assert SKILL not in [s.name for s in agent.tools.specs()]
