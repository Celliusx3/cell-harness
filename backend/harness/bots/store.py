"""The bots file, read on every call, and the chat each bot answers in."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from harness.bots.models import (
    ASSISTANT_ID,
    ASSISTANT_NAME,
    Bot,
    BotNotFound,
    BotPermanent,
    BotsFile,
)
from harness.session.log import Session
from harness.session.models import BotInstructionsEvent
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService


class BotStore:
    """Every bot, Assistant first, and the one chat each owns."""

    def __init__(
        self, path: Path, sessions: SessionService, *, assistant_instructions: str
    ) -> None:
        self._path = path
        self._sessions = sessions
        self._assistant = Bot(
            id=ASSISTANT_ID, name=ASSISTANT_NAME, instructions=assistant_instructions
        )

    async def list(self) -> tuple[Bot, ...]:
        """Assistant, then the others in the order they were made; opens Assistant's chat once."""
        bots = self._bots()
        try:
            await self._sessions.read(ASSISTANT_ID)
        except SessionNotFoundError:
            await self._open(await self._sessions.create(ASSISTANT_ID), bots[0])
        return bots

    def bot_for(self, conversation_id: str) -> Bot:
        """The bot that owns this conversation, or Assistant when none does."""
        bots = self._bots()
        return next((bot for bot in bots if bot.id == conversation_id), bots[0])

    async def create(self, name: str, instructions: str) -> Bot:
        """A new bot, with its chat already holding its instructions."""
        session = await self._sessions.create()
        bot = Bot(id=session.id, name=name, instructions=instructions)
        await self._open(session, bot)
        self._write((*self._stored(), bot))
        return bot

    def update(self, bot_id: str, name: str, instructions: str) -> Bot:
        """Rename a bot or rewrite its instructions; its chat logs them before its next turn."""
        stored = self._stored()
        known = {bot.id for bot in stored}
        if bot_id != ASSISTANT_ID and bot_id not in known:
            raise BotNotFound(bot_id)
        updated = Bot(id=bot_id, name=name, instructions=instructions)
        replaced = tuple(updated if bot.id == bot_id else bot for bot in stored)
        self._write(replaced if bot_id in known else (updated, *stored))
        return updated

    def delete(self, bot_id: str) -> None:
        """Forget a bot; its chat stays, answered as Assistant from then on."""
        if bot_id == ASSISTANT_ID:
            raise BotPermanent(bot_id)
        stored = self._stored()
        if bot_id not in {bot.id for bot in stored}:
            raise BotNotFound(bot_id)
        self._write(tuple(bot for bot in stored if bot.id != bot_id))

    def _bots(self) -> tuple[Bot, ...]:
        stored = self._stored()
        assistant = next((bot for bot in stored if bot.id == ASSISTANT_ID), self._assistant)
        return (assistant, *(bot for bot in stored if bot.id != ASSISTANT_ID))

    def _stored(self) -> tuple[Bot, ...]:
        if not self._path.exists():
            return ()
        return BotsFile.model_validate_json(self._path.read_text(encoding="utf-8")).bots

    def _write(self, bots: tuple[Bot, ...]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(BotsFile(bots=bots).model_dump_json(indent=2))
        os.replace(temp, self._path)

    async def _open(self, session: Session, bot: Bot) -> None:
        session.append(BotInstructionsEvent(name=bot.name, instructions=bot.instructions))
        await self._sessions.flush(session)
