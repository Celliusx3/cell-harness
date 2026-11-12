"""Assertions and builders shared across test modules."""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable, Sequence
from contextlib import aclosing
from datetime import UTC, datetime
from pathlib import Path

from harness.app_events import AppEventService
from harness.bots import ASSISTANT_ID, BotService
from harness.channels.links import ChatLinks, LinkCodes
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.repository import ChatRepository, ChatState
from harness.config.settings import SkillSettings
from harness.images import DiskImageRepository, ImageService
from harness.llm import AssistantMessage, Message, ToolMessage
from harness.prompts import ASSISTANT_INSTRUCTIONS
from harness.runs.run import Run
from harness.runs.service import RunService
from harness.runtime.hooks import HookChain
from harness.runtime.service import Runtime
from harness.session.log import Session
from harness.session.models import SessionHeader
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import SkillService
from harness.tickets.models import Ticket
from harness.tickets.repository import TicketRepository
from harness.tickets.service import TicketService
from harness.tickets.worker import WorkerEnd
from harness.tools import (
    ApprovalMode,
    ApprovalService,
    CallOrigin,
    Tool,
    ToolContext,
    ToolService,
    Toolset,
)
from harness.tools.client import ClientToolService
from harness.tools.service import ToolProvider
from harness.web.runtime import CLIENT_TOOLS
from tests.unit.fakes import OneModel


def unanswered_calls(messages: Sequence[Message]) -> list[str]:
    """Tool call ids with no matching tool message."""
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    return [
        call.id
        for m in messages
        if isinstance(m, AssistantMessage)
        for call in m.tool_calls
        if call.id not in answered
    ]


async def no_progress(*, percent: float | None, message: str | None) -> None:
    """A reporter that discards, for tests with nowhere to put progress."""
    return None


CONVERSATION_ID = "s"
NO_LINK_STORAGE = Path("/nonexistent/cell-harness-links")
ORIGIN = CallOrigin(bot_id="s", conversation_id=CONVERSATION_ID, mode="ask")


def context_for(
    call_id: str = "call-1", bot_id: str = "s", conversation_id: str = CONVERSATION_ID
) -> ToolContext:
    """A context for invoking a tool directly, outside the dispatcher."""
    origin = CallOrigin(bot_id=bot_id, conversation_id=conversation_id, mode="ask")
    return ToolContext(call_id=call_id, progress=no_progress, origin=origin)


def new_session(session_id: str = "s") -> Session:
    """A session with a throwaway header, for tests that only care about the log."""
    return Session(SessionHeader(id=session_id, created_at=datetime(2026, 1, 1, tzinfo=UTC)))


def no_approvals() -> ApprovalService:
    """An approval service that lists nothing, over an approvals file that cannot exist."""
    return ApprovalService(
        frozenset(), frozenset, Path("/nonexistent/cell-harness-approvals.json"), default_mode="ask"
    )


def toolset_for(
    *tools: Tool,
    providers: Sequence[ToolProvider] = (),
    offer: Sequence[str] = (),
    approvals: ApprovalService | None = None,
) -> Toolset:
    """A tool service and a toolset over `tools`, offering all of them."""
    tool_service = ToolService(tools, approvals=approvals or no_approvals(), providers=providers)
    names = [*(tool.name for tool in tools), *offer]
    return Toolset(tool_service, default_tools=names, sight_tools=frozenset())


def runtime_over(
    client,
    *tools: Tool,
    guidance: str = "",
    hooks: HookChain | None = None,
    checkpoint: Callable[[Session], Awaitable[None]] | None = None,
    context_tokens: int | None = None,
    approvals: ApprovalService | None = None,
    images: ImageService | None = None,
) -> Runtime:
    """A runtime over `tools`, with no toolset at all when there are none; no `images`, no sight."""
    return Runtime(
        models=OneModel(client, vision=images is not None, context_tokens=context_tokens),
        images=images or no_images(),
        tools=toolset_for(*tools, approvals=approvals) if tools else None,
        guidance=guidance,
        hooks=hooks if hooks is not None else HookChain(),
        checkpoint=checkpoint,
    )


async def drain(gen) -> list:
    """Everything an async iterator yields, up to `limit`."""
    async with asyncio.timeout(5):
        return [event async for event in gen]


async def cancel_mid_turn(runtime, session: Session, user_input: str = "q") -> None:
    """Run a turn in its own task and cancel it once it is blocked."""

    async def consume() -> None:
        async with aclosing(runtime.run(user_input, session=session, bot_id="b")) as events:
            async for _ in events:
                pass

    task = asyncio.create_task(consume())
    for _ in range(50):
        await asyncio.sleep(0)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def until(predicate, *, what: str) -> None:
    """Let the loop run until `predicate` holds."""
    for _ in range(500):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError(f"timed out waiting for {what}")


def durable_service(root: Path, *, prefix: str = "c") -> SessionService:
    """A session service over `root` with a fixed clock and ids `c0`, `c1`, ..."""
    ids = iter(f"{prefix}{n}" for n in range(100))
    return SessionService(
        JsonlSessionRepository(root),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )


def run_service(
    service: SessionService,
    client,
    *tools: Tool,
    context_tokens: int | None = None,
    approvals: ApprovalService | None = None,
    bots: BotService | None = None,
    images: ImageService | None = None,
) -> RunService:
    """Runs over a runtime that checkpoints through `service`, as the server wires it."""
    return RunService(
        service,
        runtime_over(
            client,
            *tools,
            checkpoint=service.flush,
            context_tokens=context_tokens,
            approvals=approvals,
            images=images,
        ),
        bots or no_bots(service),
        app_events=AppEventService(),
    )


def no_images() -> ImageService:
    """Images over a folder that cannot exist, for a model that never sees and so keeps none."""
    return ImageService(DiskImageRepository(Path("/nonexistent/cell-harness-images")))


def no_bots(service: SessionService) -> BotService:
    """Only Assistant, over a bots file that cannot exist."""
    return BotService(
        Path("/nonexistent/cell-harness-bots.json"),
        service,
        assistant_instructions=ASSISTANT_INSTRUCTIONS,
        app_events=AppEventService(),
    )


def skills_at(*roots: Path) -> SkillService:
    """A skill service over test directories, ranked as given; the last is editable."""
    return SkillService(SkillSettings(roots=roots, editable=roots[-1]))


def no_skills() -> SkillService:
    """For call sites with no `tmp_path`: a root that cannot exist."""
    return skills_at(Path("/nonexistent/cell-harness-skills"))


def client_tools() -> ClientToolService:
    """The real declarations, as the server composes them."""
    return ClientToolService(CLIENT_TOOLS, no_approvals())


def no_links() -> ChatLinks:
    """Links over codes nobody issues, and chats and bots in folders that cannot exist."""
    sessions = SessionService(JsonlSessionRepository(NO_LINK_STORAGE / "sessions"))
    chats = JsonlChatRepository(NO_LINK_STORAGE / "chats")
    return ChatLinks(chats, LinkCodes(time.monotonic), no_bots(sessions))


async def heard_nowhere(_run: Run) -> None:
    """A `follow` for an app with no chat app to hear a turn it did not start."""


async def no_worker(ticket: Ticket, *, mode: ApprovalMode) -> WorkerEnd:
    """A ticket's worker for an app that offers no `ticket_accept`: it never runs."""
    raise AssertionError(f"a test started ticket {ticket.id} without a worker")


def no_tickets(tmp_path: Path, bots: BotService, runs: RunService) -> TicketService:
    """Tickets kept under `tmp_path`, for an app whose bots are offered no `ticket_accept`."""
    return TicketService(
        TicketRepository(tmp_path / "tickets.json"),
        bots,
        runs,
        worker=no_worker,
        logs=SessionService(JsonlSessionRepository(tmp_path / "workers")),
        follow=heard_nowhere,
        now=lambda: datetime.now(UTC),
    )


async def link_to_assistant(chats: ChatRepository, channel: str, chat_id: str) -> None:
    """Store this chat's link to Assistant."""
    await chats.save(ChatState(channel=channel, chat_id=chat_id, conversation_id=ASSISTANT_ID))
