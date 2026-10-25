"""Code mode through the composition root."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.config.sections import McpServer
from harness.config.settings import MissingConfigError, Settings, load
from harness.llm import ToolCall
from harness.mcp.service import McpService
from harness.prompts import CODE_PROMPT
from harness.runtime.hooks.native.empty_reply import EmptyReplyHook
from harness.runtime.hooks.native.exact_failure import ExactFailureHook
from harness.runtime.hooks.native.no_progress import NoProgressHook
from harness.runtime.hooks.native.repeated_call import RepeatedCallHook
from harness.runtime.hooks.native.same_tool_failure import SameToolFailureHook
from harness.runtime.hooks.native.skill_list import SkillListHook
from harness.runtime.service import Runtime
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import SKILL
from harness.tools import Ok, ToolService
from harness.tools.native.bots import MESSAGE_BOT
from harness.tools.native.code_mode import EXECUTE_TYPESCRIPT, GET_FUNCTION_DETAILS, LIST_FUNCTIONS
from harness.web import runtime as composition
from harness.web.runtime import CLIENT_TOOLS, DEFAULT_TOOLS, build_runtime
from tests.unit.helpers import (
    ORIGIN,
    client_tools,
    new_session,
    no_approvals,
    no_bots,
    no_progress,
    no_skills,
)
from tests.webapp import files_in, images_in, secrets_in

WITHOUT_SKILLS = [name for name in DEFAULT_TOOLS if name not in (SKILL, MESSAGE_BOT)]


@pytest.fixture
def compose(tmp_path: Path):
    """The real object graph, with a service that is never started."""

    def build() -> Runtime:
        settings = Settings(llm={"model": "m", "api_key": "k"})
        sessions = SessionService(JsonlSessionRepository(tmp_path))
        mcp = McpService({"stub": McpServer(command="does-not-run")})
        return build_runtime(
            settings,
            sessions,
            mcp,
            no_skills(),
            client_tools(),
            no_approvals(),
            bots=no_bots(SessionService(JsonlSessionRepository(tmp_path / "bot-chats"))),
            subagent_logs=SessionService(JsonlSessionRepository(tmp_path / "subagents")),
            secrets=secrets_in(tmp_path),
            images=images_in(tmp_path),
            files=files_in(tmp_path),
        )

    return build


def test_the_request_carries_three_schemas_whatever_is_installed(compose) -> None:
    runtime = compose()

    assert runtime.tools is not None
    assert [spec.name for spec in runtime.tools.specs()] == WITHOUT_SKILLS


async def test_the_three_tools_actually_dispatch(compose) -> None:
    runtime = compose()
    assert runtime.tools is not None

    outcome = await runtime.tools.execute(
        ToolCall(id="c1", name=LIST_FUNCTIONS, arguments="{}"),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
    )

    assert isinstance(outcome, Ok)


def test_the_prompt_explains_the_three_tools(compose) -> None:
    assert CODE_PROMPT in compose().guidance


def test_the_code_prompt_names_each_code_mode_tool() -> None:
    unnamed = [
        name
        for name in (LIST_FUNCTIONS, GET_FUNCTION_DETAILS, EXECUTE_TYPESCRIPT)
        if f"`{name}`" not in CODE_PROMPT
    ]

    assert unnamed == []


def test_a_missing_deno_fails_at_startup_naming_the_fix(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_LLM__MODEL", "m")
    monkeypatch.setenv("HARNESS_LLM__API_KEY", "k")
    monkeypatch.setenv("HARNESS_CODE__DENO_PATH", "definitely-not-a-real-binary")

    with pytest.raises(MissingConfigError, match="definitely-not-a-real-binary"):
        load()


def test_exactly_one_tool_service_is_built(compose, monkeypatch) -> None:
    built: list[ToolService] = []
    real = composition.ToolService

    def spy(tools, *, approvals) -> ToolService:
        built.append(real(tools, approvals=approvals))
        return built[-1]

    monkeypatch.setattr(composition, "ToolService", spy)

    compose()

    assert len(built) == 1


def test_the_guardrail_is_installed_in_precedence_order(compose) -> None:
    runtime = compose()

    assert [type(hook) for hook in runtime.hooks.tool_hooks] == [
        ExactFailureHook,
        SameToolFailureHook,
        NoProgressHook,
        RepeatedCallHook,
    ]
    assert [type(hook) for hook in runtime.hooks.step_hooks] == [EmptyReplyHook, SkillListHook]


async def test_every_client_tool_is_offered_and_kept_from_scripts(compose) -> None:
    runtime = compose()
    assert runtime.tools is not None
    offered = {spec.name for spec in runtime.tools.specs()}
    assert CLIENT_TOOLS.names <= offered

    listed = await runtime.tools.execute(
        ToolCall(id="c1", name=LIST_FUNCTIONS, arguments="{}"),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
    )
    assert isinstance(listed, Ok)
    assert not any(name in listed.text for name in CLIENT_TOOLS.names)
