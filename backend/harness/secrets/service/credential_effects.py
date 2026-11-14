"""What a saved credential sets going: a key's bots tied, or its chat platform restarted."""

from __future__ import annotations

from dataclasses import dataclass

from harness.bots import BotService
from harness.channels.service.platforms import PlatformChannels
from harness.secrets.domain.details import ChatPlatformDetails, CredentialDetails, CustomDetails


@dataclass(frozen=True)
class CredentialEffects:
    """The bots a key serves, and the chat platforms a token signs in."""

    bots: BotService
    platforms: PlatformChannels

    async def react_to_added(
        self, name: str, details: CredentialDetails, bot_ids: tuple[str, ...]
    ) -> None:
        """Start the platform the new credential `name` signs in, or tie a key to `bot_ids`."""
        if isinstance(details, ChatPlatformDetails):
            await self.platforms.restart(details.kind)
        elif isinstance(details, CustomDetails):
            self.bots.set_bots_for_secret(name, bot_ids)

    async def react_to_changed(
        self,
        name: str,
        details: CredentialDetails,
        *,
        bot_ids: tuple[str, ...],
        is_new_key: bool,
    ) -> None:
        """Restart the platform `name` signs in on a new key, or tie a key to `bot_ids`."""
        if isinstance(details, CustomDetails):
            self.bots.set_bots_for_secret(name, bot_ids)
        elif isinstance(details, ChatPlatformDetails) and is_new_key:
            await self.platforms.restart(details.kind)

    async def react_to_removed(self, name: str, details: CredentialDetails) -> None:
        """Untie `name` from every bot, and restart the platform it signed in."""
        self.bots.forget_credential(name)
        if isinstance(details, ChatPlatformDetails):
            await self.platforms.restart(details.kind)
