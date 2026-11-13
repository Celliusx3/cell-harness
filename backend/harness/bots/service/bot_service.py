"""The bots file, read on every call: every bot, the chat each owns, and every group."""

from __future__ import annotations

from harness.app_events import AppEventService, BotsChangedAppEvent
from harness.bots.domain.models import (
    ASSISTANT_ID,
    ASSISTANT_NAME,
    BUILDER_ID,
    BUILDER_NAME,
    Bot,
    BotDraft,
    BotEdit,
    BotNotFound,
    BotPermanent,
    BotsFile,
    Group,
)
from harness.bots.repository.bot_repository import BotRepository
from harness.prompts import BUILDER_INSTRUCTIONS
from harness.session.domain.models import BotInstructionsEvent
from harness.session.log import Session
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService


class BotService:
    """Every bot, Assistant and Bot builder first, the one chat each owns, and the groups saved."""

    def __init__(
        self,
        repository: BotRepository,
        sessions: SessionService,
        *,
        assistant_instructions: str,
        app_events: AppEventService,
    ) -> None:
        self._repository = repository
        self._sessions = sessions
        self._app_events = app_events
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

    def active_bots_unopened(self) -> tuple[Bot, ...]:
        """The active bots, built-ins first, read without opening any chat."""
        return self._active_bots_in(self._read_file())

    def active_bot_names(self) -> tuple[str, ...]:
        """The active bots' names, built-ins first, read without opening any chat."""
        return tuple(bot.name for bot in self.active_bots_unopened())

    def archived_bots(self) -> tuple[Bot, ...]:
        """The archived bots, in the order they were made."""
        return tuple(bot for bot in self._read_file().bots if bot.archived)

    def active_bot(self, bot_id: str) -> Bot:
        """The active bot with this id; `BotNotFound` when there is none."""
        return self._active_bot_in(self._read_file(), bot_id)

    def groups(self) -> tuple[Group, ...]:
        """Every group, in the order each was made."""
        return self._read_file().groups

    def add_group(self, group: Group) -> None:
        """Save `group` after every group already made."""
        stored = self._read_file()
        self._write_file(stored.model_copy(update={"groups": (*stored.groups, group)}))

    def chat_of(self, bot_id: str) -> str:
        """The id of the one chat the bot answers in, which is the bot's own id."""
        return bot_id

    async def create(self, draft: BotDraft) -> Bot:
        """A new bot on the model `draft` names, with its chat already holding its instructions."""
        session = await self._sessions.create()
        bot = Bot(
            id=session.id,
            name=draft.name,
            instructions=draft.instructions,
            model_credential=draft.model,
        )
        await self._log_instructions(session, bot)
        stored = self._read_file()
        self._write_file(stored.model_copy(update={"bots": (*stored.bots, bot)}))
        return bot

    def update(self, bot_id: str, edit: BotEdit) -> Bot:
        """Set an active bot's name, instructions, model and worker limit; logged next turn."""
        stored = self._read_file()
        bot = self._active_bot_in(stored, bot_id)
        changes = {
            "name": edit.name,
            "instructions": edit.instructions,
            "model_credential": edit.model,
            "max_workers": bot.max_workers if edit.max_workers is None else edit.max_workers,
        }
        return self._save_bot(stored, bot.model_copy(update=changes))

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

    def tie_key(self, name: str, bot_ids: tuple[str, ...]) -> None:
        """Make the saved key `name` one of the keys of exactly the active bots `bot_ids`."""
        stored = self._read_file()
        changed = tuple(
            bot.with_key(name, held=bot.id in bot_ids)
            for bot in self._active_bots_in(stored)
            if bot.holds_key(name) != (bot.id in bot_ids)
        )
        self._save_bots(stored, changed)

    def forget_secret(self, secret_name: str) -> None:
        """Take `secret_name` off every stored bot, archived ones too, as a key and as a model."""
        stored = self._read_file()
        kept = tuple(bot.without_credential(secret_name) for bot in stored.bots)
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
        return self._repository.read()

    def _write_file(self, stored: BotsFile) -> None:
        self._repository.write(stored)
        self._app_events.publish(BotsChangedAppEvent())

    async def _log_instructions(self, session: Session, bot: Bot) -> None:
        session.append(bot_instructions_event(bot))
        await self._sessions.flush(session)


def bot_instructions_event(bot: Bot) -> BotInstructionsEvent:
    """The event that tells a chat's log what `bot` is called and answers with."""
    return BotInstructionsEvent(name=bot.name, instructions=bot.instructions, bot_id=bot.id)


def _without_repeats(names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(names))
