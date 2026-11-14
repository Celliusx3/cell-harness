"""Code mode through the composition root."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.config.settings import MissingConfigError, Settings, load_settings
from harness.llm import ToolCall
from harness.mcp import McpServer, McpService
from harness.prompts import CODE_PROMPT
from harness.runtime.hooks.native.empty_reply import EmptyReplyHook
from harness.runtime.hooks.native.exact_failure import ExactFailureHook
from harness.runtime.hooks.native.no_progress import NoProgressHook
from harness.runtime.hooks.native.no_wait import NoWaitHook
from harness.runtime.hooks.native.repeated_call import RepeatedCallHook
from harness.runtime.hooks.native.same_tool_failure import SameToolFailureHook
from harness.runtime.hooks.native.skill_list import SkillListHook
from harness.runtime.service import Runtime
from harness.session.repository.jsonl_session_repository import JsonlSessionRepository
from harness.session.service.session_service import SessionService
from harness.skills import SKILL
from harness.tools import Ok, ToolService
from harness.tools.native.bots import BOT_CREATE, MESSAGE_BOT
from harness.tools.native.code_mode import EXECUTE_TYPESCRIPT, GET_FUNCTION_DETAILS, LIST_FUNCTIONS
from harness.tools.native.tickets import TICKET_NOTE, TICKET_ROUTE
from harness.web import runtime as composition
from harness.web.runtime import CLIENT_TOOLS, DEFAULT_TOOLS, SCHEDULE_TOOLS, build_runtime
from tests.unit.helpers import (
    ORIGIN,
    client_tools,
    new_session,
    no_approvals,
    no_bots,
    no_progress,
    no_skills,
    worker_of,
)
from tests.webapp import files_in, images_in, secrets_in

ATTACHED_LATER = (MESSAGE_BOT, *SCHEDULE_TOOLS, BOT_CREATE, TICKET_ROUTE, TICKET_NOTE)
WITHOUT_SKILLS = [name for name in DEFAULT_TOOLS if name not in (SKILL, *ATTACHED_LATER)]


@pytest.fixture
def compose(tmp_path: Path):
    """The real object graph, with a service that is never started."""

    def build() -> Runtime:
        settings = Settings()
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


def test_the_bots_request_carries_its_default_tools_whatever_is_installed(compose) -> None:
    runtime = compose()

    assert runtime.tools is not None
    assert [spec.name for spec in runtime.tools.specs(sees_images=True)] == WITHOUT_SKILLS


async def test_the_three_tools_actually_dispatch(compose) -> None:
    runtime = worker_of(compose())
    assert runtime.tools is not None

    outcome = await runtime.tools.execute(
        ToolCall(id="c1", name=LIST_FUNCTIONS, arguments="{}"),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
        sees_images=False,
    )

    assert isinstance(outcome, Ok)


def test_a_workers_prompt_explains_the_three_tools_and_the_bots_does_not(compose) -> None:
    bot = compose()

    assert CODE_PROMPT in worker_of(bot).guidance
    assert CODE_PROMPT not in bot.guidance


def test_the_code_prompt_names_each_code_mode_tool() -> None:
    unnamed = [
        name
        for name in (LIST_FUNCTIONS, GET_FUNCTION_DETAILS, EXECUTE_TYPESCRIPT)
        if f"`{name}`" not in CODE_PROMPT
    ]

    assert unnamed == []


def test_a_missing_deno_fails_at_startup_naming_the_fix(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_CODE__DENO_PATH", "definitely-not-a-real-binary")

    with pytest.raises(MissingConfigError, match="definitely-not-a-real-binary"):
        load_settings()


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
        NoWaitHook,
        ExactFailureHook,
        SameToolFailureHook,
        NoProgressHook,
        RepeatedCallHook,
    ]
    assert [type(hook) for hook in runtime.hooks.step_hooks] == [EmptyReplyHook, SkillListHook]


async def test_every_client_tool_is_registered_not_offered_and_kept_from_scripts(compose) -> None:
    runtime = compose()
    assert runtime.tools is not None
    offered = {spec.name for spec in runtime.tools.specs(sees_images=False)}
    assert not CLIENT_TOOLS.names & offered
    assert all(runtime.tools.tool_service.get(name) for name in CLIENT_TOOLS.names)

    worker = worker_of(runtime)
    assert worker.tools is not None
    listed = await worker.tools.execute(
        ToolCall(id="c1", name=LIST_FUNCTIONS, arguments="{}"),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
        sees_images=False,
    )
    assert isinstance(listed, Ok)
    assert not any(name in listed.text for name in CLIENT_TOOLS.names)
