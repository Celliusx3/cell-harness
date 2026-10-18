"""Bots messaging bots: a message opens a turn in the other's chat, and the answer comes back."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine, Sequence

from harness.bots import Bot, BotNotFound, BotService
from harness.prompts import BOT_DID_NOT_FINISH, BOT_WAITING_ON_USER
from harness.runs.service import Run, RunService
from harness.session.models import (
    AssistantMessageEvent,
    BotMessage,
    BotMessageEvent,
    SessionEvent,
    TurnEnd,
    TurnEndReason,
    TurnStart,
)
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService
from harness.tools import INVALID_ARGUMENTS, REFUSED, Failure, Ok

logger = logging.getLogger("harness.runs")

MAX_HOPS = 6


class BotMessages:
    """Delivers each bot's message once the chat it is for is free, and each answer back."""

    def __init__(self, sessions: SessionService, bots: BotService, runs: RunService) -> None:
        self._sessions = sessions
        self._bots = bots
        self._runs = runs
        self._waiting: set[asyncio.Task[None]] = set()

    async def send(
        self, call_id: str, *, from_bot_id: str, to_name: str, text: str
    ) -> Ok | Failure:
        """Queue `text` for the active bot named `to_name`, from the turn that made `call_id`."""
        session = self._runs.session_of_call(call_id)
        if session is None or self._bots.members_of_chat(session.id).group is not None:
            return Failure(REFUSED, "message_bot works only in your own chat, not in a group chat")
        active = await self._bots.active_bots()
        recipient = next((bot for bot in active if bot.name == to_name), None)
        if recipient is None:
            return Failure(INVALID_ARGUMENTS, f"no bot is named {to_name!r}")
        if recipient.id == from_bot_id:
            return Failure(INVALID_ARGUMENTS, "you cannot send a message to yourself")
        hop = hop_of_last_turn(session.events()) + 1
        if hop > MAX_HOPS:
            return Failure(
                REFUSED,
                f"this chain of bot messages has reached {MAX_HOPS} hops, so nothing more is "
                "sent. Tell the user where things stand.",
            )
        sender = self._bots.active_bot(from_bot_id)
        request = BotMessage(
            from_bot_id=sender.id, from_name=sender.name, text=text, hop=hop, intent="request"
        )
        self._start(self._ask(recipient, request))
        return Ok(
            f"Sent to {recipient.name}. Its reply will arrive as a new message; "
            "do not send again to check on it."
        )

    async def aclose(self) -> None:
        """Cancel every delivery still waiting, for a server shutting down."""
        for task in list(self._waiting):
            task.cancel()
        await asyncio.gather(*self._waiting, return_exceptions=True)

    def _start(self, delivery: Coroutine[None, None, None]) -> None:
        task = asyncio.create_task(delivery)
        self._waiting.add(task)
        task.add_done_callback(self._waiting.discard)

    async def _ask(self, recipient: Bot, request: BotMessage) -> None:
        """Deliver `request` to `recipient`, then its final reply back to the sender."""
        run = await self._deliver(self._bots.chat_of(recipient.id), request)
        if run is None:
            return
        await _settled(run)
        result = BotMessage(
            from_bot_id=recipient.id,
            from_name=recipient.name,
            text=final_reply(run.session.events(), recipient.name),
            hop=request.hop + 1,
            intent="result",
        )
        await self._deliver(self._bots.chat_of(request.from_bot_id), result)

    async def _deliver(self, chat_id: str, message: BotMessage) -> Run | None:
        """The turn `message` opens in `chat_id` once no run is in flight there; `None` if gone."""
        try:
            while True:
                running = self._runs.active(chat_id)
                if running is not None:
                    await _settled(running)
                    continue
                session = await self._sessions.resume(chat_id)
                if self._runs.active(chat_id) is None:
                    return self._runs.hear(session, message)
        except (BotNotFound, SessionNotFoundError) as err:
            logger.warning("bot message dropped, nobody is left to answer it: %s", err)
            return None


async def _settled(run: Run) -> None:
    async with run.condition:
        await run.condition.wait_for(lambda: run.settled)


def hop_of_last_turn(events: Sequence[SessionEvent]) -> int:
    """The hop of the bot message that opened the last turn; 0 when no bot message did."""
    hop = 0
    for event in events:
        if isinstance(event, TurnStart):
            hop = 0
        elif isinstance(event, BotMessageEvent):
            hop = event.message.hop
    return hop


def final_reply(events: Sequence[SessionEvent], name: str) -> str:
    """What the last turn ended by saying when it completed; else why `name` has no answer."""
    said = ""
    reason: TurnEndReason | None = None
    for event in events:
        if isinstance(event, TurnStart):
            said, reason = "", None
        elif isinstance(event, AssistantMessageEvent):
            said = event.message.content
        elif isinstance(event, TurnEnd):
            reason = event.reason
    if reason == "completed":
        return said
    if reason == "pending":
        return BOT_WAITING_ON_USER.format(name=name)
    return BOT_DID_NOT_FINISH.format(name=name)
