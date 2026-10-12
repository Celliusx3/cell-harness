"""The bots file, read on every call, and who answers in each chat."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from harness.bots.models import (
    ASSISTANT_ID,
    ASSISTANT_NAME,
    BUILDER_ID,
    BUILDER_NAME,
    Bot,
    BotNotFound,
    BotPermanent,
    BotsFile,
    ChatMembers,
    Group,
    GroupDraft,
)
from harness.prompts import BUILDER_INSTRUCTIONS
from harness.session.log import Session
from harness.session.models import BotInstructionsEvent, GroupMembersEvent
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService


class BotService:
    """Every bot, Assistant and Bot builder first, the one chat each owns, and every group."""

    def __init__(
        self, path: Path, sessions: SessionService, *, assistant_instructions: str
    ) -> None:
        self._path = path
        self._sessions = sessions
        self._built_ins = (
            Bot(id=ASSISTANT_ID, name=ASSISTANT_NAME, instructions=assistant_instructions),
            Bot(id=BUILDER_ID, name=BUILDER_NAME, instructions=BUILDER_INSTRUCTIONS),
        )
        self._built_in_ids = frozenset(bot.id for bot in self._built_ins)

    async def active_bots(self) -> tuple[Bot, ...]:
        """The built-ins, then the active others in the order made; opens a built-in's chat once."""
        bots = self._active_bots()
        for bot in bots[: len(self._built_ins)]:
            try:
                await self._sessions.read(bot.id)
            except SessionNotFoundError:
                await self._log_instructions(await self._sessions.create(bot.id), bot)
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

    def members_of_chat(self, chat_id: str) -> ChatMembers:
        """A bot's chat's bot, or a group's active members in order; `BotNotFound` for neither."""
        active = self._active_bots()
        own = next((bot for bot in active if bot.id == chat_id), None)
        if own is not None:
            return ChatMembers(group=None, bots=(own,))
        group = next((group for group in self.groups() if group.id == chat_id), None)
        if group is None:
            raise BotNotFound(chat_id)
        by_id = {bot.id: bot for bot in active}
        return ChatMembers(
            group=group, bots=tuple(by_id[bot_id] for bot_id in group.member_ids if bot_id in by_id)
        )

    def asker(self, session: Session, call_id: str) -> Bot:
        """The member whose turn asked for `call_id`; the chat's only bot in an older log."""
        members = self.members_of_chat(session.id).bots
        bot_id = session.speaker_of_call(call_id)
        asking = members if bot_id is None else tuple(bot for bot in members if bot.id == bot_id)
        if len(asking) != 1:
            raise BotNotFound(bot_id if bot_id is not None else session.id)
        return asking[0]

    def groups(self) -> tuple[Group, ...]:
        """Every group, in the order each was made."""
        return self._stored().groups

    async def create_group(self, draft: GroupDraft) -> Group:
        """A new group of active bots, its chat holding its members; `BotNotFound` for any other."""
        members = tuple(self.find(bot_id) for bot_id in draft.member_ids)
        session = await self._sessions.create()
        group = Group(id=session.id, name=draft.name, member_ids=draft.member_ids)
        session.append(roster(group, members))
        await self._sessions.flush(session)
        stored = self._stored()
        self._save(stored.model_copy(update={"groups": (*stored.groups, group)}))
        return group

    def chat_of(self, bot_id: str) -> str:
        """The id of the one chat the bot answers in, which is the bot's own id."""
        return bot_id

    async def create(self, name: str, instructions: str) -> Bot:
        """A new bot, with its chat already holding its instructions."""
        session = await self._sessions.create()
        bot = Bot(id=session.id, name=name, instructions=instructions)
        await self._log_instructions(session, bot)
        self._write((*self._stored_bots(), bot))
        return bot

    def update(self, bot_id: str, name: str, instructions: str) -> Bot:
        """Edit an active bot's name or instructions; its chat logs them before its next turn."""
        bot = self.find(bot_id)
        return self._store(bot.model_copy(update={"name": name, "instructions": instructions}))

    def allow_secret(self, bot_id: str, name: str) -> Bot:
        """Add the saved key `name` to the keys an active bot may use."""
        bot = self.find(bot_id)
        return self._store(
            bot.model_copy(update={"secret_names": _once_each((*bot.secret_names, name))})
        )

    def set_allowed_secrets(self, bot_id: str, names: tuple[str, ...]) -> Bot:
        """Make `names` the saved keys an active bot may use, and no others."""
        bot = self.find(bot_id)
        return self._store(bot.model_copy(update={"secret_names": _once_each(names)}))

    def forget_secret(self, name: str) -> None:
        """Take the key `name` off the list of every stored bot, archived ones too."""
        stored = self._stored_bots()
        kept = tuple(
            bot.model_copy(update={"secret_names": tuple(n for n in bot.secret_names if n != name)})
            for bot in stored
        )
        if kept != stored:
            self._write(kept)

    def check_removable(self, bot_id: str) -> None:
        """Refuse a built-in with `BotPermanent` and an unknown bot with `BotNotFound`."""
        if bot_id in self._built_in_ids:
            raise BotPermanent(bot_id)
        if bot_id not in {bot.id for bot in self._stored_bots()}:
            raise BotNotFound(bot_id)

    def archive(self, bot_id: str) -> None:
        """Hide a bot and its chat until it is restored."""
        self.check_removable(bot_id)
        self._set_archived(bot_id, archived=True)

    def restore(self, bot_id: str) -> None:
        """Bring an archived bot back with its chat as it was; an active one stays as it is."""
        if bot_id not in self._built_in_ids:
            self._set_archived(bot_id, archived=False)

    async def delete(self, bot_id: str) -> None:
        """Remove a bot and its chat for good."""
        self.check_removable(bot_id)
        self._write(tuple(bot for bot in self._stored_bots() if bot.id != bot_id))
        await self._sessions.delete(bot_id)

    def _active_bots(self) -> tuple[Bot, ...]:
        stored = self._stored_bots()
        built_ins = (
            next((bot for bot in stored if bot.id == default.id), default)
            for default in self._built_ins
        )
        others = (bot for bot in stored if bot.id not in self._built_in_ids and not bot.archived)
        return (*built_ins, *others)

    def _store(self, updated: Bot) -> Bot:
        stored = self._stored_bots()
        replaced = tuple(updated if bot.id == updated.id else bot for bot in stored)
        self._write(replaced if updated.id in {bot.id for bot in stored} else (updated, *stored))
        return updated

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

    def _stored(self) -> BotsFile:
        if not self._path.exists():
            return BotsFile()
        return BotsFile.model_validate_json(self._path.read_text(encoding="utf-8"))

    def _stored_bots(self) -> tuple[Bot, ...]:
        return self._stored().bots

    def _write(self, bots: tuple[Bot, ...]) -> None:
        self._save(self._stored().model_copy(update={"bots": bots}))

    def _save(self, stored: BotsFile) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(stored.model_dump_json(indent=2))
        os.replace(temp, self._path)

    async def _log_instructions(self, session: Session, bot: Bot) -> None:
        session.append(
            BotInstructionsEvent(name=bot.name, instructions=bot.instructions, bot_id=bot.id)
        )
        await self._sessions.flush(session)


def roster(group: Group, members: tuple[Bot, ...]) -> GroupMembersEvent:
    """The group's name and its members' names, as its chat logs them for its bots."""
    return GroupMembersEvent(name=group.name, members=tuple(bot.name for bot in members))


def _once_each(names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(names))
