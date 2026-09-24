"""The `create-skill` skill: it loads, and the examples it teaches are ones that work."""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

from harness.config.sections import McpServer
from harness.config.settings import Settings
from harness.llm.messages import ToolCall
from harness.mcp.store import McpServerStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import parse
from harness.tools.definition import Ok
from harness.tools.native.code import EXECUTE
from harness.web.agent import build_agent
from tests.unit.helpers import client_tools, no_gate, no_progress, skills_at

PROJECT_SKILLS = Path(__file__).parents[3] / ".agents" / "skills"
CREATE_SKILL = PROJECT_SKILLS / "create-skill" / "SKILL.md"


def fenced(text: str, language: str) -> str:
    """The first fenced block of `language` in `text`, dedented."""
    found = re.search(rf"^([ \t]*)```{language}\n(.*?)^\1```", text, re.MULTILINE | re.DOTALL)
    assert found is not None, f"no ```{language} block"
    return textwrap.dedent(found.group(2))


def test_it_loads_from_the_project_root() -> None:
    snapshot = skills_at(PROJECT_SKILLS).snapshot()

    assert "create-skill" in [skill.name for skill in snapshot.skills]
    assert not [p for p in snapshot.problems if "create-skill" in str(p.path)]


def test_the_example_skill_it_teaches_is_one_the_page_would_save() -> None:
    example = parse(fenced(CREATE_SKILL.read_text(), "markdown"))

    assert example.frontmatter.name == "unit-convert"
    assert 'skill({ name: "unit-convert", path: "scripts/convert.ts" })' in example.body
    assert "execute_typescript({ code:" in example.body


async def test_the_example_script_it_teaches_runs_as_a_program(tmp_path: Path) -> None:
    agent = build_agent(
        Settings(llm={"model": "m", "api_key": "k"}),
        SessionService(JsonlSessionRepository(tmp_path)),
        McpServerStore({"stub": McpServer(command="does-not-run")}),
        skills_at(tmp_path / "skills"),
        client_tools(),
        no_gate(),
    )
    assert agent.tools is not None
    script = fenced(CREATE_SKILL.read_text(), "ts")

    ran = await agent.tools.execute(
        ToolCall(
            id="c1",
            name=EXECUTE,
            arguments=json.dumps({"code": script, "description": "the example script"}),
        ),
        progress=no_progress,
    )

    assert isinstance(ran, Ok), ran
    assert isinstance(ran.data, dict) and ran.data["result"] == 3.106855
