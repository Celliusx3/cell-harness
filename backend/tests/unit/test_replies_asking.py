"""A chat is asked about each waiting call, in order, and a refused ask spares the rest."""

from __future__ import annotations

import asyncio
from pathlib import Path

from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.llm.messages import ToolCall
from harness.llm.stream import Completed, ToolCallChunk
from harness.tools.approval import ApprovalGate
from harness.tools.client import PendingCall
from harness.tools.definition import Ok, ToolDefinition, ToolOutcome
from tests.unit.fakes import EchoArgs, SteppedClient, completed
from tests.unit.helpers import durable_service, no_skills, run_store

PLATFORM = "fake"
CHAT = "7"
WRITE = "memory__write_note"


class AskingPlatform:
    """Records which calls it was asked about; refuses the ones it is told to."""

    channel = PLATFORM
    on_missing = "recreate"

    def __init__(self, refused: frozenset[str] = frozenset()) -> None:
        self.asked: list[str] = []
        self._refused = refused

    async def run(self) -> None:
        await asyncio.Event().wait()

    async def send_message(self, chat_id: str, text: str) -> None:
        return None

    async def send_typing(self, chat_id: str) -> None:
        return None

    async def send_link(self, chat_id: str, text: str, url: str) -> None:
        return None

    async def ask_client(self, chat_id: str, request: PendingCall, url: str) -> None:
        if request.call_id in self._refused:
            raise RuntimeError("the platform refused the ask")
        self.asked.append(request.call_id)


def _writer() -> ToolDefinition[EchoArgs]:
    async def execute(args: EchoArgs, _context) -> ToolOutcome:
        return Ok(content=f"saved {args.value}")

    return ToolDefinition.from_model(
        name=WRITE, description="Save a note.", args_model=EchoArgs, execute=execute
    )


async def _two_waiting(tmp_path: Path, platform: AskingPlatform) -> None:
    calls = tuple(ToolCall(id=f"w{n}", name=WRITE, arguments=f'{{"value": "{n}"}}') for n in (1, 2))
    step = [*(ToolCallChunk(call=c) for c in calls), Completed(full_text="", tool_calls=calls)]
    sessions = durable_service(tmp_path / "sessions")
    gate = ApprovalGate(frozenset({WRITE}), frozenset, tmp_path / "approvals.json")
    runs = run_store(sessions, SteppedClient(step, completed("never")), _writer(), gate=gate)
    chats = JsonlChatRepository(tmp_path / "chats")
    gateway = ChannelGateway(chats, runs, sessions, no_skills(), public_url="http://t")
    gateway.register(platform)

    await gateway.receive(InboundMessage(channel=PLATFORM, chat_id=CHAT, text="save two notes"))
    for _ in range(200):
        task = gateway._tasks.get((PLATFORM, CHAT))
        if (task is None or task.done()) and not any(runs._runs.values()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("the chat never went idle")


async def test_the_waiting_calls_are_asked_in_the_order_they_were_made(tmp_path) -> None:
    platform = AskingPlatform()

    await _two_waiting(tmp_path, platform)

    assert platform.asked == ["w1", "w2"]


async def test_a_refused_ask_does_not_stop_the_next(tmp_path) -> None:
    platform = AskingPlatform(refused=frozenset({"w1"}))

    await _two_waiting(tmp_path, platform)

    assert platform.asked == ["w2"]
