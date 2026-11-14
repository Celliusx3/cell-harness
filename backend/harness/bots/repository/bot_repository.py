"""`bots.json`: its bots, fetched and changed one at a time, the file replaced whole."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from harness.bots.domain.models import Bot, BotNotFound, BotsFile


class BotRepository:
    """The stored bots of one file; a missing file holds none."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def bots(self) -> tuple[Bot, ...]:
        """Every stored bot, in stored order."""
        return self._read().bots

    def find(self, bot_id: str) -> Bot:
        """The stored bot with this id, archived or not; `BotNotFound` when there is none."""
        found = next((bot for bot in self._read().bots if bot.id == bot_id), None)
        if found is None:
            raise BotNotFound(bot_id)
        return found

    def add(self, bot: Bot) -> None:
        """Store a new bot after every stored bot."""
        stored = self._read()
        self._write(stored.model_copy(update={"bots": (*stored.bots, bot)}))

    def update(self, *bots: Bot) -> None:
        """Swap in each of `bots` for the stored bot with its id; those not stored yet go first."""
        stored = self._read()
        by_id = {bot.id: bot for bot in bots}
        stored_ids = {bot.id for bot in stored.bots}
        added = tuple(bot for bot in bots if bot.id not in stored_ids)
        replaced = tuple(by_id.get(bot.id, bot) for bot in stored.bots)
        self._write(stored.model_copy(update={"bots": (*added, *replaced)}))

    def delete(self, bot_id: str) -> None:
        """Remove the stored bot with this id; an unknown id changes nothing."""
        stored = self._read()
        kept = tuple(bot for bot in stored.bots if bot.id != bot_id)
        self._write(stored.model_copy(update={"bots": kept}))

    def _read(self) -> BotsFile:
        if not self._path.exists():
            return BotsFile()
        return BotsFile.model_validate_json(self._path.read_text(encoding="utf-8"))

    def _write(self, stored: BotsFile) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(stored.model_dump_json(indent=2))
        os.replace(temp, self._path)
