"""Bots messaging bots: a message opens a turn in the other's chat, and the answer comes back."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine

from harness.bots import Bot, BotNotFound, BotService
from harness.prompts import MESSAGE_TO_YOURSELF
from harness.runs.domain.bot_message_log import MAX_HOPS, final_reply, hop_of_last_turn
from harness.runs.service.run import Run
from harness.runs.service.run_service import RunService
from harness.session.domain.models import BotMessage
from harness.session.repository.session_repository import SessionNotFoundError
from harness.tools import INVALID_ARGUMENTS, REFUSED, Failure, Ok

logger = logging.getLogger("harness.runs")

Follow = Callable[[Run], Awaitable[None]]


class BotMessageService:
    """Delivers each bot's message once the chat it is for is free, and each answer back."""

    def __init__(self, bots: BotService, runs: RunService, *, follow: Follow) -> None:
        self._bots = bots
        self._runs = runs
        self._follow = follow
        self._waiting: set[asyncio.Task[None]] = set()

    async def send(
        self, call_id: str, *, from_bot_id: str, to_name: str, text: str
    ) -> Ok | Failure:
        """Queue `text` for the active bot named `to_name`, from the turn that made `call_id`."""
        session = self._runs.session_of_call(call_id)
        if session is None or self._runs.groups.chat_members(session.id).group is not None:
            return Failure(REFUSED, "message_bot works only in your own chat, not in a group chat")
        active = self._bots.active_bots()
        recipient = next((bot for bot in active if bot.name == to_name), None)
        if recipient is None:
            return Failure(INVALID_ARGUMENTS, f"no bot is named {to_name!r}")
        if recipient.id == from_bot_id:
            return Failure(INVALID_ARGUMENTS, MESSAGE_TO_YOURSELF.format(name=recipient.name))
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
        run = await self.deliver(recipient.id, request)
        if run is None:
            return
        await run.wait_until_settled()
        result = BotMessage(
            from_bot_id=recipient.id,
            from_name=recipient.name,
            text=final_reply(run.session.events(), recipient.name),
            hop=request.hop + 1,
            intent="result",
        )
        await self.deliver(request.from_bot_id, result)

    async def deliver(self, bot_id: str, message: BotMessage) -> Run | None:
        """The turn `message` opens in `bot_id`'s own chat once free, heard by its chat apps."""
        try:
            chat_id = self._bots.chat_of(bot_id)
            run = await self._runs.hear_when_free(chat_id, message, speaker_id=bot_id)
        except (BotNotFound, SessionNotFoundError) as err:
            logger.warning("bot message dropped, nobody is left to answer it: %s", err)
            return None
        await self._follow(run)
        return run
