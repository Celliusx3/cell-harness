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


class BotService:
    """Every bot, Assistant first, and the one chat each owns."""

    def __init__(
        self, path: Path, sessions: SessionService, *, assistant_instructions: str
    ) -> None:
        self._path = path
        self._sessions = sessions
        self._assistant = Bot(
            id=ASSISTANT_ID, name=ASSISTANT_NAME, instructions=assistant_instructions
        )

    async def active_bots(self) -> tuple[Bot, ...]:
        """Assistant, then the active others in the order made; opens Assistant's chat once."""
        bots = self._active_bots()
        try:
            await self._sessions.read(ASSISTANT_ID)
        except SessionNotFoundError:
            await self._log_instructions(await self._sessions.create(ASSISTANT_ID), bots[0])
        return bots

    def archived_bots(self) -> tuple[Bot, ...]:
        """The archived bots, in the order they were made."""
        return tuple(bot for bot in self._stored_bots() if bot.archived)

    def find(self, bot_id: str) -> Bot:
        """The active bot with this id; `BotNotFound` when there is none."""
        bot = next((bot for bot in self._active_bots() if bot.id == bot_id), None)
        if bot is None:
            raise BotNotFound(bot_id)
        return bot

    async def create(self, name: str, instructions: str) -> Bot:
        """A new bot, with its chat already holding its instructions."""
        session = await self._sessions.create()
        bot = Bot(id=session.id, name=name, instructions=instructions)
        await self._log_instructions(session, bot)
        self._write((*self._stored_bots(), bot))
        return bot

    def update(self, bot_id: str, name: str, instructions: str) -> Bot:
        """Edit an active bot's name or instructions; its chat logs them before its next turn."""
        updated = self.find(bot_id).model_copy(update={"name": name, "instructions": instructions})
        stored = self._stored_bots()
        replaced = tuple(updated if bot.id == bot_id else bot for bot in stored)
        self._write(replaced if bot_id in {bot.id for bot in stored} else (updated, *stored))
        return updated

    def check_removable(self, bot_id: str) -> None:
        """Refuse Assistant with `BotPermanent` and an unknown bot with `BotNotFound`."""
        if bot_id == ASSISTANT_ID:
            raise BotPermanent(bot_id)
        if bot_id not in {bot.id for bot in self._stored_bots()}:
            raise BotNotFound(bot_id)

    def archive(self, bot_id: str) -> None:
        """Hide a bot and its chat until it is restored."""
        self.check_removable(bot_id)
        self._set_archived(bot_id, archived=True)

    def restore(self, bot_id: str) -> None:
        """Bring an archived bot back with its chat as it was; an active one stays as it is."""
        if bot_id != ASSISTANT_ID:
            self._set_archived(bot_id, archived=False)

    async def delete(self, bot_id: str) -> None:
        """Remove a bot and its chat for good."""
        self.check_removable(bot_id)
        self._write(tuple(bot for bot in self._stored_bots() if bot.id != bot_id))
        await self._sessions.delete(bot_id)

    def _active_bots(self) -> tuple[Bot, ...]:
        stored = self._stored_bots()
        assistant = next((bot for bot in stored if bot.id == ASSISTANT_ID), self._assistant)
        others = (bot for bot in stored if bot.id != ASSISTANT_ID and not bot.archived)
        return (assistant, *others)

    def _set_archived(self, bot_id: str, *, archived: bool) -> None:
        stored = self._stored_bots()
        if bot_id not in {bot.id for bot in stored}:
            raise BotNotFound(bot_id)
        self._write(
            tuple(
                bot.model_copy(update={"archived": archived}) if bot.id == bot_id else bot
                for bot in stored
            )
        )

    def _stored_bots(self) -> tuple[Bot, ...]:
        if not self._path.exists():
            return ()
        return BotsFile.model_validate_json(self._path.read_text(encoding="utf-8")).bots

    def _write(self, bots: tuple[Bot, ...]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(BotsFile(bots=bots).model_dump_json(indent=2))
        os.replace(temp, self._path)

    async def _log_instructions(self, session: Session, bot: Bot) -> None:
        session.append(BotInstructionsEvent(name=bot.name, instructions=bot.instructions))
        await self._sessions.flush(session)
