"""Code mode through the composition root.

`build_agent` is where the setting, the registry, the pipeline and the prompt
meet. A mis-wire there is invisible everywhere else — every piece works and the
model is simply offered the wrong things — so these assert on what the agent
actually presents.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.agent.hooks.native.exact_failure import ExactFailureHook
from harness.agent.hooks.native.no_progress import NoProgressHook
from harness.agent.hooks.native.repeated_call import RepeatedCallHook
from harness.agent.hooks.native.same_tool_failure import SameToolFailureHook
from harness.agent.loop import LoopAgent
from harness.config.settings import McpServer, MissingConfigError, Settings, load
from harness.llm.messages import ToolCall
from harness.mcp.store import McpServerStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import SKILL, SkillSnapshot
from harness.tools.definition import Ok
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.native.code import CODE_PROMPT, LIST
from harness.web import server
from harness.web.server import DEFAULT_TOOLS, build_agent
from tests.unit.helpers import no_progress

# What a request carries when no skill exists: `SKILL` is in `DEFAULT_TOOLS` but
# its provider yields nothing, and the pipeline skips an absent name.
WITHOUT_SKILLS = [name for name in DEFAULT_TOOLS if name != SKILL]


@pytest.fixture
def compose(tmp_path: Path):
    """The real object graph, with a store that is never started so it publishes
    no tools — the question here is the wiring, not a server's catalog."""

    def build() -> LoopAgent:
        settings = Settings(llm={"model": "m", "api_key": "k"})
        sessions = SessionService(JsonlSessionRepository(tmp_path))
        mcp = McpServerStore({"stub": McpServer(command="does-not-run")})
        return build_agent(settings, sessions, mcp, SkillSnapshot)

    return build


def test_the_request_carries_three_schemas_whatever_is_installed(compose) -> None:
    """The headline property: a server added tomorrow changes nothing about what
    the model is offered. It discovers everything from inside a program."""
    agent = compose()

    assert agent.tools is not None
    assert [spec.name for spec in agent.tools.specs()] == WITHOUT_SKILLS


async def test_the_three_tools_actually_dispatch(compose) -> None:
    """Offered is not enough. They are registered like any other tool, which is
    what keeps the loop and the log unaware that code mode exists — and an
    unregistered one would come back as UNKNOWN_TOOL, not as a wiring error."""
    agent = compose()
    assert agent.tools is not None

    outcome = await agent.tools.execute(
        ToolCall(id="c1", name=LIST, arguments="{}"), progress=no_progress
    )

    assert isinstance(outcome, Ok)


def test_the_prompt_explains_the_three_tools(compose) -> None:
    """Prompt text is code. Three unfamiliar tools and no explanation is a model
    that answers "I can't do that" rather than discovering its capabilities."""
    assert CODE_PROMPT in compose().system_prompt


# ── the runtime is a requirement, not an option ───────────────────────────────


def test_a_missing_deno_fails_at_startup_naming_the_fix(monkeypatch) -> None:
    """Every tool call goes through the sandbox, so a harness without it has no
    capabilities at all. Better a startup error naming the install than a
    confusing tool failure on the first script."""
    monkeypatch.setenv("HARNESS_LLM__MODEL", "m")
    monkeypatch.setenv("HARNESS_LLM__API_KEY", "k")
    monkeypatch.setenv("HARNESS_CODE__DENO_PATH", "definitely-not-a-real-binary")

    with pytest.raises(MissingConfigError, match="definitely-not-a-real-binary"):
        load()


def test_exactly_one_dispatcher_is_built(compose, monkeypatch) -> None:
    """The property this whole split protects.

    Phase 12 installs an approval gate on the dispatcher. A second instance would
    let the gate cover the model and miss scripts — or the reverse — and nothing
    else in the suite would notice. Counting constructions says that directly,
    without reaching into anyone's closures.
    """
    built: list[ToolDispatcher] = []
    real = server.ToolDispatcher

    def spy(registry) -> ToolDispatcher:
        built.append(real(registry))
        return built[-1]

    monkeypatch.setattr(server, "ToolDispatcher", spy)

    compose()

    assert len(built) == 1


def test_the_guardrail_is_installed_in_precedence_order(compose) -> None:
    """Acceptance: the guardrail is one registration at the root — specific
    before general, so the first detector with something to say wins."""
    agent = compose()

    assert [type(hook) for hook in agent.hooks.hooks] == [
        ExactFailureHook,
        SameToolFailureHook,
        NoProgressHook,
        RepeatedCallHook,
    ]
