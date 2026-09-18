"""Assertions and builders shared across test modules.

`unanswered_calls` lives here rather than in `harness/` because nothing in the
product calls it: the loop knows what it owes from the calls it dispatched, so a
check derived from history would be a second answer to a settled question. It is
how *tests* prove the loop's repair path worked.

When phase 3 loads a log it did not build, a real runtime check earns its place —
and belongs with `resume`, which is the code that would act on it.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Sequence
from contextlib import aclosing
from datetime import UTC, datetime
from pathlib import Path

from harness.agent.compaction import CompactionService
from harness.agent.hooks import HookChain
from harness.agent.loop import LoopAgent
from harness.config.settings import SkillSettings
from harness.llm.messages import AssistantMessage, Message, ToolMessage
from harness.runs.store import RunStore
from harness.session.log import Session
from harness.session.models import SessionHeader
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import SkillService
from harness.tools.client import ClientToolService
from harness.tools.context import ToolContext
from harness.tools.definition import ToolDefinition
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolProvider, ToolRegistry
from harness.web.agent import CLIENT_TOOLS


def unanswered_calls(messages: Sequence[Message]) -> list[str]:
    """Tool call ids with no matching tool message.

    Empty when the history is one a provider will accept. Non-empty means a turn
    died between asking and answering, which a provider rejects outright rather
    than tolerating.

    `Sequence`, not `Iterable`: this reads `messages` twice, and a generator
    would be exhausted by the first pass — leaving the second to find no calls
    and report a broken history as fine. An assertion that fails open is worse
    than no assertion, so the type says what the body actually needs.
    """
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    return [
        call.id
        for m in messages
        if isinstance(m, AssistantMessage)
        for call in m.tool_calls
        if call.id not in answered
    ]


async def no_progress(*, percent: float | None, message: str | None) -> None:
    """A reporter that discards, for tests with nowhere to put progress.

    Lives here, not in `harness/`, because the product never needs one: the loop
    always has a real queue to report into. `ToolProgressReporter` is required
    rather than defaulted at every call site precisely so a *caller* that forgets
    one is a type error, not progress that silently never arrives.
    """
    return None


def context_for(call_id: str = "call-1") -> ToolContext:
    """A context for invoking a tool directly, outside the dispatcher."""
    return ToolContext(call_id=call_id, progress=no_progress)


def new_session(session_id: str = "s") -> Session:
    """A session with a throwaway header, for tests that only care about the log.

    `created_at` is fixed rather than `now()` so a header that leaks into an
    assertion compares equal across runs.
    """
    return Session(SessionHeader(id=session_id, created_at=datetime(2026, 1, 1, tzinfo=UTC)))


def pipeline_for(
    *tools: ToolDefinition,
    providers: Sequence[ToolProvider] = (),
    offer: Sequence[str] = (),
) -> ToolPipeline:
    """A registry, a dispatcher and a pipeline over `tools`, offering all of them.

    The three arguments are required in the product so nobody inherits a tool
    list or a second dispatcher by accident. Tests that do not care about either
    say so once, here, rather than at every construction. `offer` names tools a
    provider will contribute later, so they are in the list when they arrive.
    """
    registry = ToolRegistry(tools, providers=providers)
    names = [*(tool.name for tool in tools), *offer]
    return ToolPipeline(registry, ToolDispatcher(registry), default_tools=names)


def loop_agent(
    client,
    *tools: ToolDefinition,
    system_prompt: str = "",
    hooks: HookChain | None = None,
    checkpoint: Callable[[Session], Awaitable[None]] | None = None,
    compaction: CompactionService | None = None,
) -> LoopAgent:
    """An agent over `tools`, with no pipeline at all when there are none —
    so a bare agent sends `tools: None`, not an empty list."""
    return LoopAgent(
        name="t",
        model="m",
        client=client,
        tools=pipeline_for(*tools) if tools else None,
        system_prompt=system_prompt,
        hooks=hooks if hooks is not None else HookChain(),
        checkpoint=checkpoint,
        compaction=compaction,
    )


async def drain(gen) -> list:
    """Everything an async iterator yields, bounded: the loop has no step cap, so
    a script that never stops calling a tool would otherwise hang the suite
    rather than fail a test."""
    async with asyncio.timeout(5):
        return [event async for event in gen]


async def cancel_mid_turn(agent_, session: Session, user_input: str = "q") -> None:
    """Run a turn in its own task and cancel it once it is blocked inside a
    tool or a hanging stream, the way a closed tab does. A task rather than a
    `break`, because the consumer is *blocked*: there is no next event."""

    async def consume() -> None:
        async with aclosing(agent_.run(user_input, session=session)) as events:
            async for _ in events:
                pass

    task = asyncio.create_task(consume())
    for _ in range(50):
        await asyncio.sleep(0)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def until(predicate, *, what: str) -> None:
    """Let the loop run until `predicate` holds.

    Polling rather than an event, because what is being waited for is a *third
    party's* progress — the loop appending to a log it owns — and there is no
    hook for it that would not exist purely for tests.
    """
    for _ in range(500):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError(f"timed out waiting for {what}")


def durable_service(root: Path, *, prefix: str = "c") -> SessionService:
    """A session service over `root` with a fixed clock and predictable ids
    (`c0`, `c1`, …), so a test can name the conversation it just made."""
    ids = iter(f"{prefix}{n}" for n in range(100))
    return SessionService(
        JsonlSessionRepository(root),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )


def run_store(
    service: SessionService,
    client,
    *tools: ToolDefinition,
    compaction: CompactionService | None = None,
) -> RunStore:
    """Runs over an agent that checkpoints through `service`, as the server wires it."""
    return RunStore(
        service, loop_agent(client, *tools, checkpoint=service.flush, compaction=compaction)
    )


def skills_at(*roots: Path) -> SkillService:
    """A skill service over test directories, ranked as given; the last is the
    editable one, as `~/.agents/skills` is in config.json. A root that does not
    exist is simply empty."""
    return SkillService(SkillSettings(roots=roots, editable=roots[-1]))


def no_skills() -> SkillService:
    """For call sites with no `tmp_path`: a root that cannot exist."""
    return skills_at(Path("/nonexistent/cell-harness-skills"))


def client_tools() -> ClientToolService:
    """The real declarations, as the server composes them."""
    return ClientToolService(CLIENT_TOOLS)
