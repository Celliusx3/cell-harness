"""Each bot's model: its LLM credential from the keyring, or `NoModel` when it has none."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from harness.bots import BotNotFound, BotService
from harness.config.sections import LLMSettings
from harness.llm import LLMClient
from harness.llm.adapters import OpenAISettings
from harness.runtime.models import ModelChoice, NoModel
from harness.secrets import SecretName, SecretService, UnsealedModelCredential


@dataclass(frozen=True)
class ModelEndpoint:
    """What a credential's settings are made into: a client for its requests, and its window."""

    client_for: Callable[[OpenAISettings], LLMClient]
    blocking_window_for: Callable[[OpenAISettings], int | None]


@dataclass(frozen=True)
class CachedChoice:
    """A credential's model choice, and the record id of the saved version it was made from."""

    version: str
    choice: ModelChoice


def client_settings_for(credential: UnsealedModelCredential, base: LLMSettings) -> OpenAISettings:
    """`credential`'s endpoint, model and key, asked as `base` says every model is asked."""
    details = credential.details
    return OpenAISettings(
        base_url=details.base_url,
        model=details.model,
        api_key=credential.key.get_secret_value(),
        temperature=base.temperature,
        timeout_seconds=base.timeout_seconds,
    )


class CredentialModels:
    """A bot's LLM credential as its model and window, made once per version; else `NoModel`."""

    def __init__(
        self,
        secrets: SecretService,
        bots: BotService,
        base: LLMSettings,
        endpoint: ModelEndpoint,
    ) -> None:
        self._secrets = secrets
        self._bots = bots
        self._base = base
        self._endpoint = endpoint
        self._by_credential: dict[str, CachedChoice] = {}

    async def model_for(self, bot_id: str | None) -> ModelChoice | NoModel:
        """`bot_id`'s LLM credential; `NoModel` for no bot, an unknown one, or one with none."""
        name = self._credential_of(bot_id)
        own = None if name is None else await self._choice_named(name)
        return NoModel() if own is None else own

    def _credential_of(self, bot_id: str | None) -> SecretName | None:
        if bot_id is None:
            return None
        try:
            return self._bots.active_bot(bot_id).model_credential
        except BotNotFound:
            return None

    async def _choice_named(self, name: str) -> ModelChoice | None:
        """The LLM credential `name` as a model, unsealed and asked its window per version."""
        version = self._secrets.model_credential_version(name)
        if version is None:
            return None
        cached = self._by_credential.get(name)
        if cached is not None and cached.version == version:
            return cached.choice
        credential = await asyncio.to_thread(self._secrets.model_credential_named, name)
        if credential is None:
            return None
        settings = client_settings_for(credential, self._base)
        window = await asyncio.to_thread(self._endpoint.blocking_window_for, settings)
        details = credential.details
        choice = ModelChoice(
            self._endpoint.client_for(settings), details.model, details.vision, window
        )
        self._by_credential[name] = CachedChoice(version=version, choice=choice)
        return choice
