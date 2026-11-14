"""The bots file, read on every call: every bot, and the chat each owns."""

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
    BuiltInBotError,
)
from harness.bots.repository.bot_repository import BotRepository
from harness.prompts import BUILDER_INSTRUCTIONS
from harness.session.domain.log import Session
from harness.session.domain.models import BotInstructionsEvent
from harness.session.service.session_service import SessionService


class BotService:
    """Every bot, Assistant and Bot builder first, and the one chat each owns."""

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

    def active_bots(self) -> tuple[Bot, ...]:
        """The built-ins, then the active others in the order made."""
        return _active_bots(self._repository.bots(), self._built_ins)

    def archived_bots(self) -> tuple[Bot, ...]:
        """The archived bots, in the order they were made."""
        return tuple(bot for bot in self._repository.bots() if bot.archived)

    def active_bot(self, bot_id: str) -> Bot:
        """The active bot with this id; `BotNotFound` when there is none."""
        bot = next((bot for bot in self.active_bots() if bot.id == bot_id), None)
        if bot is None:
            raise BotNotFound(bot_id)
        return bot

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
        self._repository.add(bot)
        self._publish_change()
        return bot

    def update(self, bot_id: str, edit: BotEdit) -> Bot:
        """Set an active bot's name, instructions, model and worker limit; logged next turn."""
        changes = {
            "name": edit.name,
            "instructions": edit.instructions,
            "model_credential": edit.model,
            "max_workers": edit.max_workers,
        }
        edited = self.active_bot(bot_id).model_copy(update=changes)
        self._repository.update(edited)
        self._publish_change()
        return edited

    def allow_secret(self, bot_id: str, secret_name: str) -> Bot:
        """Add the saved key `secret_name` to the keys an active bot may use."""
        bot = self.active_bot(bot_id)
        allowed = bot.model_copy(
            update={"secret_names": _without_repeats((*bot.secret_names, secret_name))}
        )
        self._repository.update(allowed)
        self._publish_change()
        return allowed

    def set_allowed_secrets(self, bot_id: str, secret_names: tuple[str, ...]) -> Bot:
        """Make `secret_names` the saved keys an active bot may use, and no others."""
        bot = self.active_bot(bot_id)
        allowed = bot.model_copy(update={"secret_names": _without_repeats(secret_names)})
        self._repository.update(allowed)
        self._publish_change()
        return allowed

    def set_bots_for_secret(self, name: str, bot_ids: tuple[str, ...]) -> None:
        """Make the saved key `name` one of the keys of exactly the active bots `bot_ids`."""
        changed = tuple(
            bot.with_secret(name, allowed=bot.id in bot_ids)
            for bot in self.active_bots()
            if bot.can_use_secret(name) != (bot.id in bot_ids)
        )
        self._repository.update(*changed)
        self._publish_change()

    def forget_credential(self, credential_name: str) -> None:
        """Take `credential_name` off every stored bot, archived too, as a key and as a model."""
        stored = self._repository.bots()
        cleared = (bot.without_credential(credential_name) for bot in stored)
        changed = tuple(bot for bot in cleared if bot not in stored)
        if changed:
            self._repository.update(*changed)
            self._publish_change()

    def archive(self, bot_id: str) -> None:
        """Hide a bot and its chat until it is restored."""
        stored = self._removable_bot(bot_id)
        self._repository.update(stored.model_copy(update={"archived": True}))
        self._publish_change()

    def restore(self, bot_id: str) -> None:
        """Bring an archived bot back with its chat as it was; an active one stays as it is."""
        if bot_id not in self._built_in_ids:
            stored = self._repository.find(bot_id)
            self._repository.update(stored.model_copy(update={"archived": False}))
            self._publish_change()

    async def delete(self, bot_id: str) -> None:
        """Remove a bot and its chat for good."""
        self._repository.delete(self._removable_bot(bot_id).id)
        self._publish_change()
        await self._sessions.delete(self.chat_of(bot_id))

    def _removable_bot(self, bot_id: str) -> Bot:
        if bot_id in self._built_in_ids:
            raise BuiltInBotError(bot_id)
        return self._repository.find(bot_id)

    def _publish_change(self) -> None:
        self._app_events.publish(BotsChangedAppEvent())

    async def _log_instructions(self, session: Session, bot: Bot) -> None:
        session.append(bot_instructions_event(bot))
        await self._sessions.flush(session)


def bot_instructions_event(bot: Bot) -> BotInstructionsEvent:
    """The event that tells a chat's log what `bot` is called and answers with."""
    return BotInstructionsEvent(name=bot.name, instructions=bot.instructions, bot_id=bot.id)


def _active_bots(stored: tuple[Bot, ...], built_ins: tuple[Bot, ...]) -> tuple[Bot, ...]:
    built_in_ids = {default.id for default in built_ins}
    stored_built_ins = (
        next((bot for bot in stored if bot.id == default.id), default) for default in built_ins
    )
    others = (bot for bot in stored if bot.id not in built_in_ids and not bot.archived)
    return (*stored_built_ins, *others)


def _without_repeats(names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(names))
