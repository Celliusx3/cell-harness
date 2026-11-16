"""The tickets the server composes: `ticket_route` for every bot, `ticket_report` for workers."""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Protocol

from harness.bots import Bot, BotService
from harness.prompts import CODE_PROMPT, GUIDANCE
from harness.runs.service.bot_messages import Follow
from harness.runs.service.chat_grants import ChatGrantLog
from harness.runs.service.run_service import RunService
from harness.runtime.hooks.native.no_wait import NoWaitHook
from harness.runtime.service import Runtime
from harness.session.service.session_service import SessionService
from harness.skills import SkillService
from harness.tickets.repository.ticket_repository import TicketRepository
from harness.tickets.service.ticket_service import TicketService
from harness.tickets.service.worker import RuntimeTicketWorker
from harness.tools import ChatGrants, ToolService, Toolset
from harness.tools.native.files import ASK_ABOUT_IMAGE_JOBS, ASK_ABOUT_IMAGES, VIEW_IMAGE
from harness.tools.native.tickets import (
    TICKET_REPORT,
    ticket_note_tool,
    ticket_report_tool,
    ticket_route_tool,
)
from harness.tools.service.tool_service import Disposer
from harness.web.runtime import CODE_TOOLS, SIGHT_TOOLS, SKILL_WRITE_TOOLS, WORK_TOOLS

WORKER_TOOLS = (
    *CODE_TOOLS,
    *WORK_TOOLS,
    *SKILL_WRITE_TOOLS,
    VIEW_IMAGE,
    ASK_ABOUT_IMAGES,
    ASK_ABOUT_IMAGE_JOBS,
    TICKET_REPORT,
)


class BotLookup(Protocol):
    """A bot's chat and its settings, as a ticket's worker needs them."""

    def chat_of(self, bot_id: str) -> str: ...

    def active_bot(self, bot_id: str) -> Bot: ...


def ticket_workers(
    tool_service: ToolService,
    runtime: Runtime,
    logs: SessionService,
    bots: BotLookup,
    *,
    chat_grants: ChatGrants,
    skills: SkillService,
    offered_from_start: Callable[[], frozenset[str]],
) -> RuntimeTicketWorker:
    """`runtime` as each ticket's worker runs it, in its bot's chat and under its grants."""
    worker = dataclasses.replace(
        delegate_runtime(tool_service, runtime, WORKER_TOOLS, chat_grants, offered_from_start),
        guidance=GUIDANCE,
        chat_id_for=lambda _session, bot_id: bots.chat_of(bot_id),
    )
    return RuntimeTicketWorker(
        worker, logs, lambda bot_id: bots.active_bot(bot_id).max_workers, skills
    )


def delegate_runtime(
    tool_service: ToolService,
    runtime: Runtime,
    tools: Sequence[str],
    chat_grants: ChatGrants,
    offered_from_start: Callable[[], frozenset[str]],
) -> Runtime:
    """`runtime` as a ticket's worker runs it: offered `tools` and the servers' tools offered from
    the start, free to wait, its chat's grants."""
    hooks = runtime.hooks
    kept = tuple(hook for hook in hooks.tool_hooks if not isinstance(hook, NoWaitHook))
    toolset = Toolset(
        tool_service,
        tools,
        sight_tools=SIGHT_TOOLS,
        can_reach_servers=True,
        chat_grants=chat_grants,
        offered_from_start=offered_from_start,
    )
    return dataclasses.replace(
        runtime,
        tools=toolset,
        guidance=CODE_PROMPT,
        hooks=dataclasses.replace(hooks, tool_hooks=kept),
    )


def attach_tickets(tool_service: ToolService, tickets: TicketService) -> Disposer:
    """`ticket_route`, `ticket_note` and `ticket_report` offered from `tool_service`."""
    return tool_service.add_provider(
        lambda: [ticket_route_tool(tickets), ticket_note_tool(tickets), ticket_report_tool()]
    )


def ticket_service(
    tickets_path: Path,
    runtime: Runtime,
    logs: SessionService,
    bots: BotService,
    runs: RunService,
    *,
    sessions: SessionService,
    skills: SkillService,
    offered_from_start: Callable[[], frozenset[str]],
    follow: Follow,
    now: Callable[[], datetime],
) -> TicketService:
    """The tickets kept at `tickets_path`, each run by a worker of `runtime` under its chat's
    grants, with the ticket tools offered to `runtime`."""
    assert runtime.tools is not None
    tool_service = runtime.tools.tool_service
    worker = ticket_workers(
        tool_service,
        runtime,
        logs,
        bots,
        chat_grants=ChatGrantLog(runs, sessions),
        skills=skills,
        offered_from_start=offered_from_start,
    )
    tickets = TicketService(
        TicketRepository(tickets_path),
        bots,
        runs,
        worker=worker,
        logs=logs,
        follow=follow,
        now=now,
        ids=lambda: uuid.uuid4().hex,
    )
    attach_tickets(tool_service, tickets)
    return tickets
