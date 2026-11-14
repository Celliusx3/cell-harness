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
    BotsFile,
    BuiltInBotError,
    Group,
)
from harness.bots.repository.bot_repository import BotRepository
from harness.prompts import BUILDER_INSTRUCTIONS
from harness.session.domain.log import Session
from harness.session.domain.models import BotInstructionsEvent
from harness.session.service.session_service import SessionService


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

    async def open_active_bots(self) -> tuple[Bot, ...]:
        """The built-ins, then the active others in the order made; creates no chat."""
        return self.active_bots()

    def active_bots(self) -> tuple[Bot, ...]:
        """The active bots, built-ins first, read without opening any chat."""
        return self._repository.read().active_bots(self._built_ins)

    def archived_bots(self) -> tuple[Bot, ...]:
        """The archived bots, in the order they were made."""
        return tuple(bot for bot in self._repository.read().bots if bot.archived)

    def active_bot(self, bot_id: str) -> Bot:
        """The active bot with this id; `BotNotFound` when there is none."""
        return self._active_bot_in(self._repository.read(), bot_id)

    def groups(self) -> tuple[Group, ...]:
        """Every group, in the order each was made."""
        return self._repository.read().groups

    def add_group(self, group: Group) -> None:
        """Save `group` after every group already made."""
        stored = self._repository.read()
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
        stored = self._repository.read()
        self._write_file(stored.model_copy(update={"bots": (*stored.bots, bot)}))
        return bot

    def update(self, bot_id: str, edit: BotEdit) -> Bot:
        """Set an active bot's name, instructions, model and worker limit; logged next turn."""
        stored = self._repository.read()
        bot = self._active_bot_in(stored, bot_id)
        changes = {
            "name": edit.name,
            "instructions": edit.instructions,
            "model_credential": edit.model,
            "max_workers": edit.max_workers,
        }
        edited = bot.model_copy(update=changes)
        self._write_file(stored.with_bots((edited,)))
        return edited

    def allow_secret(self, bot_id: str, secret_name: str) -> Bot:
        """Add the saved key `secret_name` to the keys an active bot may use."""
        stored = self._repository.read()
        bot = self._active_bot_in(stored, bot_id)
        allowed = bot.model_copy(
            update={"secret_names": _without_repeats((*bot.secret_names, secret_name))}
        )
        self._write_file(stored.with_bots((allowed,)))
        return allowed

    def set_allowed_secrets(self, bot_id: str, secret_names: tuple[str, ...]) -> Bot:
        """Make `secret_names` the saved keys an active bot may use, and no others."""
        stored = self._repository.read()
        bot = self._active_bot_in(stored, bot_id)
        allowed = bot.model_copy(update={"secret_names": _without_repeats(secret_names)})
        self._write_file(stored.with_bots((allowed,)))
        return allowed

    def set_bots_for_secret(self, name: str, bot_ids: tuple[str, ...]) -> None:
        """Make the saved key `name` one of the keys of exactly the active bots `bot_ids`."""
        stored = self._repository.read()
        changed = tuple(
            bot.with_secret(name, allowed=bot.id in bot_ids)
            for bot in stored.active_bots(self._built_ins)
            if bot.can_use_secret(name) != (bot.id in bot_ids)
        )
        self._write_file(stored.with_bots(changed))

    def forget_credential(self, secret_name: str) -> None:
        """Take `secret_name` off every stored bot, archived ones too, as a key and as a model."""
        stored = self._repository.read()
        bots = tuple(bot.without_credential(secret_name) for bot in stored.bots)
        if bots != stored.bots:
            self._write_file(stored.model_copy(update={"bots": bots}))

    def archive(self, bot_id: str) -> None:
        """Hide a bot and its chat until it is restored."""
        stored = self._repository.read()
        self._check_removable(stored, bot_id)
        self._write_file(stored.with_archived(bot_id, archived=True))

    def restore(self, bot_id: str) -> None:
        """Bring an archived bot back with its chat as it was; an active one stays as it is."""
        if bot_id not in self._built_in_ids:
            self._write_file(self._repository.read().with_archived(bot_id, archived=False))

    async def delete(self, bot_id: str) -> None:
        """Remove a bot and its chat for good."""
        stored = self._repository.read()
        self._check_removable(stored, bot_id)
        kept = tuple(bot for bot in stored.bots if bot.id != bot_id)
        self._write_file(stored.model_copy(update={"bots": kept}))
        await self._sessions.delete(self.chat_of(bot_id))

    def _active_bot_in(self, stored: BotsFile, bot_id: str) -> Bot:
        active = stored.active_bots(self._built_ins)
        bot = next((bot for bot in active if bot.id == bot_id), None)
        if bot is None:
            raise BotNotFound(bot_id)
        return bot

    def _check_removable(self, stored: BotsFile, bot_id: str) -> None:
        if bot_id in self._built_in_ids:
            raise BuiltInBotError(bot_id)
        if bot_id not in {bot.id for bot in stored.bots}:
            raise BotNotFound(bot_id)

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
