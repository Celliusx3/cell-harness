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
from harness.tools.native.skills import SKILL_DELETE, SKILL_SAVE, SKILL_WRITE_FILE
from harness.web.agent import DEFAULT_TOOLS, build_agent
from tests.unit.helpers import client_tools, no_gate, no_progress, skills_at

COMMITTED_CONFIG = Path(__file__).parents[2] / "config.json"


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
        return build_agent(settings, sessions, mcp, skills_at(root), client_tools(), no_gate())

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


def test_every_skill_write_is_offered_before_any_skill_exists(compose) -> None:
    build, _ = compose
    agent = build()
    assert agent.tools is not None

    offered = [s.name for s in agent.tools.specs()]

    assert {SKILL_SAVE, SKILL_DELETE, SKILL_WRITE_FILE} <= set(offered)


async def test_a_script_cannot_write_a_skill(compose) -> None:
    build, root = compose
    write_skill(root, "pdf")
    agent = build()
    assert agent.tools is not None

    listed = await agent.tools.execute(
        ToolCall(id="c1", name=LIST, arguments="{}"), progress=no_progress
    )
    assert isinstance(listed, Ok)
    assert not any(name in listed.text for name in (SKILL_SAVE, SKILL_DELETE, SKILL_WRITE_FILE))

    ran = await agent.tools.execute(
        ToolCall(
            id="c2",
            name=EXECUTE,
            arguments=json.dumps(
                {"code": 'return await skill_delete({name: "pdf"});', "description": "try"}
            ),
        ),
        progress=no_progress,
    )
    assert "skill_delete is not defined" in str(ran) or "cannot be called" in str(ran)
    assert (root / "pdf" / "SKILL.md").exists()


def test_the_committed_config_asks_before_any_skill_write() -> None:
    committed = json.loads(COMMITTED_CONFIG.read_text())

    assert {SKILL_SAVE, SKILL_DELETE, SKILL_WRITE_FILE} <= set(committed["approval"]["tools"])


async def test_a_script_written_into_a_skill_runs_as_a_program(compose) -> None:
    build, root = compose
    agent = build()
    assert agent.tools is not None
    skills_at(root).save("convert", "---\ndescription: Converts km to miles.\n---\nRun it.\n")

    wrote = await agent.tools.execute(
        ToolCall(
            id="c1",
            name=SKILL_WRITE_FILE,
            arguments=json.dumps(
                {
                    "name": "convert",
                    "path": "scripts/km.ts",
                    "text": "return Math.round(5 * 0.621371 * 1000) / 1000;",
                }
            ),
        ),
        progress=no_progress,
    )
    assert isinstance(wrote, Ok)

    read = await agent.tools.execute(
        ToolCall(
            id="c2", name=SKILL, arguments=json.dumps({"name": "convert", "path": "scripts/km.ts"})
        ),
        progress=no_progress,
    )
    assert isinstance(read, Ok)
    script = read.text.split("\n", 1)[1].rsplit("\n</skill_file>", 1)[0]

    ran = await agent.tools.execute(
        ToolCall(
            id="c3",
            name=EXECUTE,
            arguments=json.dumps({"code": script, "description": "run the skill's script"}),
        ),
        progress=no_progress,
    )
    assert isinstance(ran, Ok) and ran.data == 3.107
