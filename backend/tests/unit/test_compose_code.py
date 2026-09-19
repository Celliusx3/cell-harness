"""Code mode through the composition root."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.agent.hooks.native.exact_failure import ExactFailureHook
from harness.agent.hooks.native.no_progress import NoProgressHook
from harness.agent.hooks.native.repeated_call import RepeatedCallHook
from harness.agent.hooks.native.same_tool_failure import SameToolFailureHook
from harness.agent.loop import LoopAgent
from harness.config.sections import McpServer
from harness.config.settings import MissingConfigError, Settings, load
from harness.llm.messages import ToolCall
from harness.mcp.store import McpServerStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import SKILL
from harness.tools.definition import Ok
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.native.code import CODE_PROMPT, LIST
from harness.web import agent as composition
from harness.web.agent import CLIENT_TOOLS, DEFAULT_TOOLS, build_agent
from tests.unit.helpers import client_tools, no_progress, no_skills

WITHOUT_SKILLS = [name for name in DEFAULT_TOOLS if name != SKILL]


@pytest.fixture
def compose(tmp_path: Path):
    """The real object graph, with a store that is never started."""

    def build() -> LoopAgent:
        settings = Settings(llm={"model": "m", "api_key": "k"})
        sessions = SessionService(JsonlSessionRepository(tmp_path))
        mcp = McpServerStore({"stub": McpServer(command="does-not-run")})
        return build_agent(settings, sessions, mcp, no_skills(), client_tools())

    return build


def test_the_request_carries_three_schemas_whatever_is_installed(compose) -> None:
    agent = compose()

    assert agent.tools is not None
    assert [spec.name for spec in agent.tools.specs()] == WITHOUT_SKILLS


async def test_the_three_tools_actually_dispatch(compose) -> None:
    agent = compose()
    assert agent.tools is not None

    outcome = await agent.tools.execute(
        ToolCall(id="c1", name=LIST, arguments="{}"), progress=no_progress
    )

    assert isinstance(outcome, Ok)


def test_the_prompt_explains_the_three_tools(compose) -> None:
    assert CODE_PROMPT in compose().system_prompt


def test_a_missing_deno_fails_at_startup_naming_the_fix(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_LLM__MODEL", "m")
    monkeypatch.setenv("HARNESS_LLM__API_KEY", "k")
    monkeypatch.setenv("HARNESS_CODE__DENO_PATH", "definitely-not-a-real-binary")

    with pytest.raises(MissingConfigError, match="definitely-not-a-real-binary"):
        load()


def test_exactly_one_dispatcher_is_built(compose, monkeypatch) -> None:
    built: list[ToolDispatcher] = []
    real = composition.ToolDispatcher

    def spy(registry) -> ToolDispatcher:
        built.append(real(registry))
        return built[-1]

    monkeypatch.setattr(composition, "ToolDispatcher", spy)

    compose()

    assert len(built) == 1


def test_the_guardrail_is_installed_in_precedence_order(compose) -> None:
    agent = compose()

    assert [type(hook) for hook in agent.hooks.hooks] == [
        ExactFailureHook,
        SameToolFailureHook,
        NoProgressHook,
        RepeatedCallHook,
    ]


async def test_every_client_tool_is_offered_and_kept_from_scripts(compose) -> None:
    agent = compose()
    assert agent.tools is not None
    offered = {spec.name for spec in agent.tools.specs()}
    assert CLIENT_TOOLS.names <= offered

    listed = await agent.tools.execute(
        ToolCall(id="c1", name=LIST, arguments="{}"), progress=no_progress
    )
    assert isinstance(listed, Ok)
    assert not any(name in listed.text for name in CLIENT_TOOLS.names)
