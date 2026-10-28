"""The bots file, read on every call, and who answers in each chat."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from harness.bots import _turn_order, ties
from harness.bots.models import (
    ASSISTANT_ID,
    ASSISTANT_NAME,
    BUILDER_ID,
    BUILDER_NAME,
    Bot,
    BotDraft,
    BotNotFound,
    BotPermanent,
    BotsFile,
    ChatMembers,
    Group,
    GroupDraft,
    GroupEmpty,
)
from harness.bots.ties import TiedKind
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
        bots = self._active_bots_in(self._read_file())
        for bot in bots[: len(self._built_ins)]:
            try:
                await self._sessions.read(bot.id)
            except SessionNotFoundError:
                await self._log_instructions(await self._sessions.create(bot.id), bot)
        return bots

    def active_bot_names(self) -> tuple[str, ...]:
        """The active bots' names, built-ins first, read without opening any chat."""
        return tuple(bot.name for bot in self._active_bots_in(self._read_file()))

    def archived_bots(self) -> tuple[Bot, ...]:
        """The archived bots, in the order they were made."""
        return tuple(bot for bot in self._read_file().bots if bot.archived)

    def active_bot(self, bot_id: str) -> Bot:
        """The active bot with this id; `BotNotFound` when there is none."""
        return self._active_bot_in(self._read_file(), bot_id)

    def members_of_chat(self, chat_id: str) -> ChatMembers:
        """A bot's chat's bot, or a group's active members in order; `BotNotFound` for neither."""
        stored = self._read_file()
        active = self._active_bots_in(stored)
        own = next((bot for bot in active if self.chat_of(bot.id) == chat_id), None)
        if own is not None:
            return ChatMembers(group=None, bots=(own,))
        group = next((group for group in stored.groups if group.id == chat_id), None)
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

    def first_speaker(self, session: Session, text: str) -> Bot:
        """Who answers `text` first, its instructions and group logged; `GroupEmpty` if none can."""
        members = self.members_of_chat(session.id)
        speakers = _turn_order.first_speakers(text, members.bots)
        if not speakers:
            raise GroupEmpty(session.id)
        _log_speaker_if_changed(session, members, speakers[0])
        return speakers[0]

    def next_speaker(self, session: Session) -> Bot | None:
        """Who the queue says is next, its instructions and group logged; `None` when nobody is."""
        members = self.members_of_chat(session.id)
        speaker = _turn_order.next_speaker(session.events(), members.bots)
        if speaker is None:
            return None
        _log_speaker_if_changed(session, members, speaker)
        return speaker

    def groups(self) -> tuple[Group, ...]:
        """Every group, in the order each was made."""
        return self._read_file().groups

    async def create_group(self, draft: GroupDraft) -> Group:
        """A new group of active bots, its chat holding its members; `BotNotFound` for any other."""
        before = self._read_file()
        members = tuple(self._active_bot_in(before, bot_id) for bot_id in draft.member_ids)
        session = await self._sessions.create()
        group = Group(id=session.id, name=draft.name, member_ids=draft.member_ids)
        session.append(_group_members_event(group, members))
        await self._sessions.flush(session)
        stored = self._read_file()
        self._write_file(stored.model_copy(update={"groups": (*stored.groups, group)}))
        return group

    def chat_of(self, bot_id: str) -> str:
        """The id of the one chat the bot answers in, which is the bot's own id."""
        return bot_id

    async def create(self, draft: BotDraft) -> Bot:
        """A new bot, with its chat already holding its instructions."""
        session = await self._sessions.create()
        bot = Bot(id=session.id, name=draft.name, instructions=draft.instructions)
        await self._log_instructions(session, bot)
        stored = self._read_file()
        self._write_file(stored.model_copy(update={"bots": (*stored.bots, bot)}))
        return bot

    def update(self, bot_id: str, draft: BotDraft) -> Bot:
        """Edit an active bot's name or instructions; its chat logs them before its next turn."""
        stored = self._read_file()
        bot = self._active_bot_in(stored, bot_id)
        return self._save_bot(
            stored, bot.model_copy(update={"name": draft.name, "instructions": draft.instructions})
        )

    def allow_secret(self, bot_id: str, secret_name: str) -> Bot:
        """Add the saved key `secret_name` to the keys an active bot may use."""
        stored = self._read_file()
        bot = self._active_bot_in(stored, bot_id)
        return self._save_bot(
            stored,
            bot.model_copy(
                update={"secret_names": _without_repeats((*bot.secret_names, secret_name))}
            ),
        )

    def set_allowed_secrets(self, bot_id: str, secret_names: tuple[str, ...]) -> Bot:
        """Make `secret_names` the saved keys an active bot may use, and no others."""
        stored = self._read_file()
        bot = self._active_bot_in(stored, bot_id)
        return self._save_bot(
            stored, bot.model_copy(update={"secret_names": _without_repeats(secret_names)})
        )

    def tie_credential(self, name: str, kind: TiedKind, bot_ids: tuple[str, ...]) -> None:
        """Make the credential `name` serve exactly the active bots `bot_ids`, and save them."""
        stored = self._read_file()
        self._save_bots(stored, ties.retied_bots(self._active_bots_in(stored), name, kind, bot_ids))

    def forget_secret(self, secret_name: str) -> None:
        """Take `secret_name` off every stored bot, archived ones too, as a key and as a model."""
        stored = self._read_file()
        kept = tuple(ties.untied_bot(bot, secret_name) for bot in stored.bots)
        if kept != stored.bots:
            self._write_file(stored.model_copy(update={"bots": kept}))

    def archive(self, bot_id: str) -> None:
        """Hide a bot and its chat until it is restored."""
        stored = self._read_file()
        self._check_removable(stored, bot_id)
        self._set_archived(stored, bot_id, archived=True)

    def restore(self, bot_id: str) -> None:
        """Bring an archived bot back with its chat as it was; an active one stays as it is."""
        if bot_id not in self._built_in_ids:
            self._set_archived(self._read_file(), bot_id, archived=False)

    async def delete(self, bot_id: str) -> None:
        """Remove a bot and its chat for good."""
        stored = self._read_file()
        self._check_removable(stored, bot_id)
        kept = tuple(bot for bot in stored.bots if bot.id != bot_id)
        self._write_file(stored.model_copy(update={"bots": kept}))
        await self._sessions.delete(bot_id)

    def _active_bots_in(self, stored: BotsFile) -> tuple[Bot, ...]:
        built_ins = (
            next((bot for bot in stored.bots if bot.id == default.id), default)
            for default in self._built_ins
        )
        others = (
            bot for bot in stored.bots if bot.id not in self._built_in_ids and not bot.archived
        )
        return (*built_ins, *others)

    def _active_bot_in(self, stored: BotsFile, bot_id: str) -> Bot:
        bot = next((bot for bot in self._active_bots_in(stored) if bot.id == bot_id), None)
        if bot is None:
            raise BotNotFound(bot_id)
        return bot

    def _check_removable(self, stored: BotsFile, bot_id: str) -> None:
        if bot_id in self._built_in_ids:
            raise BotPermanent(bot_id)
        if bot_id not in {bot.id for bot in stored.bots}:
            raise BotNotFound(bot_id)

    def _save_bot(self, stored: BotsFile, bot: Bot) -> Bot:
        self._save_bots(stored, (bot,))
        return bot

    def _save_bots(self, stored: BotsFile, bots: tuple[Bot, ...]) -> None:
        by_id = {bot.id: bot for bot in bots}
        stored_ids = {saved.id for saved in stored.bots}
        added = tuple(bot for bot in bots if bot.id not in stored_ids)
        replaced = tuple(by_id.get(saved.id, saved) for saved in stored.bots)
        self._write_file(stored.model_copy(update={"bots": (*added, *replaced)}))

    def _set_archived(self, stored: BotsFile, bot_id: str, *, archived: bool) -> None:
        if bot_id not in {bot.id for bot in stored.bots}:
            raise BotNotFound(bot_id)
        bots = tuple(
            bot.model_copy(update={"archived": archived}) if bot.id == bot_id else bot
            for bot in stored.bots
        )
        self._write_file(stored.model_copy(update={"bots": bots}))

    def _read_file(self) -> BotsFile:
        if not self._path.exists():
            return BotsFile()
        return BotsFile.model_validate_json(self._path.read_text(encoding="utf-8"))

    def _write_file(self, stored: BotsFile) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(stored.model_dump_json(indent=2))
        os.replace(temp, self._path)

    async def _log_instructions(self, session: Session, bot: Bot) -> None:
        session.append(_bot_instructions_event(bot))
        await self._sessions.flush(session)


def _log_speaker_if_changed(session: Session, members: ChatMembers, bot: Bot) -> None:
    logged = session.bot_instructions(bot.id)
    if logged is None or (logged.name, logged.instructions) != (bot.name, bot.instructions):
        session.append(_bot_instructions_event(bot))
    if members.group is not None:
        members_now = _group_members_event(members.group, members.bots)
        if session.group_members() != members_now:
            session.append(members_now)


def _bot_instructions_event(bot: Bot) -> BotInstructionsEvent:
    return BotInstructionsEvent(name=bot.name, instructions=bot.instructions, bot_id=bot.id)


def _group_members_event(group: Group, members: tuple[Bot, ...]) -> GroupMembersEvent:
    return GroupMembersEvent(name=group.name, members=tuple(bot.name for bot in members))


def _without_repeats(names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(names))
