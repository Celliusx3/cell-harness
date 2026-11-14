"""The changes a person makes to a bot, and what each sets going across the app."""

from __future__ import annotations

from dataclasses import dataclass

from harness.bots.domain.models import Bot, BotDraft, BotEdit, UnsavedModelError
from harness.bots.service.bot_service import BotService
from harness.runs.service.run_service import RunService
from harness.schedules import ScheduleService
from harness.secrets import SecretName, SecretNotFound, SecretService


@dataclass(frozen=True)
class BotLifecycleService:
    """A bot made, edited, archived or deleted, with its model, keys, turns and schedules."""

    bots: BotService
    runs: RunService
    secrets: SecretService
    schedules: ScheduleService

    async def create(self, draft: BotDraft) -> Bot:
        """A new bot on the saved LLM credential `draft` names; `UnsavedModelError` otherwise."""
        self._refuse_unsaved_model(draft.model)
        return await self.bots.create(draft)

    def update(self, bot_id: str, edit: BotEdit) -> Bot:
        """The bot as `edit` leaves it, on a saved LLM credential or on no model."""
        self._refuse_unsaved_model(edit.model)
        return self.bots.update(bot_id, edit)

    def set_allowed_secrets(self, bot_id: str, names: tuple[str, ...]) -> Bot:
        """Make the saved custom keys `names` the bot's keys; `SecretNotFound` for any other."""
        saved = {summary.name for summary in self.secrets.custom_key_summaries()}
        unsaved = next((name for name in names if name not in saved), None)
        if unsaved is not None:
            raise SecretNotFound(unsaved)
        return self.bots.set_allowed_secrets(bot_id, names)

    async def archive(self, bot_id: str) -> None:
        """Hide the bot and its chat, and stop its turns."""
        self.bots.archive(bot_id)
        await self._stop_speaking(bot_id)

    async def delete(self, bot_id: str) -> None:
        """Stop the bot's turns, then remove it, its chat and its schedules for good."""
        self.bots.archive(bot_id)
        await self._stop_speaking(bot_id)
        await self.bots.delete(bot_id)
        self.schedules.delete_of_bot(bot_id)

    def _refuse_unsaved_model(self, name: SecretName | None) -> None:
        """Raise when `name` is not a saved LLM credential; `None` is no model, and passes."""
        reason = None if name is None else self.secrets.not_a_model_reason(name)
        if reason is not None:
            raise UnsavedModelError(reason)

    async def _stop_speaking(self, bot_id: str) -> None:
        """End the bot's own chat's turn, and the discussion of any group it is speaking in."""
        for chat_id in {self.bots.chat_of(bot_id), *self.runs.chats_spoken_in(bot_id)}:
            await self.runs.stop(chat_id)
