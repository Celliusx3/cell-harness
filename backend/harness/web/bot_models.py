"""Each bot's model: its LLM credential from the keyring, or the Default model."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from harness.bots import BotNotFound, BotService
from harness.config.sections import LLMSettings
from harness.llm import LLMClient
from harness.runtime.models import ModelChoice
from harness.secrets import SecretName, SecretService, UnsealedModelCredential


@dataclass(frozen=True)
class CachedChoice:
    """A credential's model choice, and the record id of the saved version it was made from."""

    version: str
    choice: ModelChoice


class CredentialModels:
    """A bot's LLM credential as its model, made once per saved version; else the Default model."""

    def __init__(
        self,
        secrets: SecretService,
        bots: BotService,
        default: LLMSettings,
        client_for: Callable[[LLMSettings], LLMClient],
    ) -> None:
        self._secrets = secrets
        self._bots = bots
        self._default_settings = default
        self._client_for = client_for
        self._default: ModelChoice | None = None
        self._by_credential: dict[str, CachedChoice] = {}

    async def model_for(self, bot_id: str | None) -> ModelChoice:
        """`bot_id`'s LLM credential; the Default for no bot, an unknown one, or one with none."""
        name = self._credential_of(bot_id)
        version = None if name is None else self._secrets.model_credential_version(name)
        if name is None or version is None:
            return self._default_choice()
        cached = self._by_credential.get(name)
        if cached is not None and cached.version == version:
            return cached.choice
        credential = await asyncio.to_thread(self._secrets.model_credential_named, name)
        if credential is None:
            return self._default_choice()
        choice = self._choice_of(credential)
        self._by_credential[name] = CachedChoice(version=version, choice=choice)
        return choice

    def _credential_of(self, bot_id: str | None) -> SecretName | None:
        if bot_id is None:
            return None
        try:
            return self._bots.active_bot(bot_id).model_credential
        except BotNotFound:
            return None

    def _default_choice(self) -> ModelChoice:
        if self._default is None:
            settings = self._default_settings
            self._default = ModelChoice(self._client_for(settings), settings.model)
        return self._default

    def _choice_of(self, credential: UnsealedModelCredential) -> ModelChoice:
        details = credential.details
        settings = self._default_settings.model_copy(
            update={
                "base_url": details.base_url,
                "model": details.model,
                "api_key": credential.key.get_secret_value(),
            }
        )
        return ModelChoice(self._client_for(settings), details.model)
