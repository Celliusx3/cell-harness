"""What a saved credential sets going: a key's bots tied, its platform or capability restarted."""

from __future__ import annotations

from dataclasses import dataclass

from harness.bots import BotService
from harness.mcp import McpService
from harness.secrets.models.details import (
    CapabilityDetails,
    ChatPlatformDetails,
    CredentialDetails,
    CustomDetails,
)
from harness.web.platforms import PlatformChannels


@dataclass(frozen=True)
class CredentialEffects:
    """The bots a key serves, the chat platforms a token signs in, the capabilities a key starts."""

    bots: BotService
    platforms: PlatformChannels
    mcp: McpService

    def capability_refusal(self, details: CredentialDetails) -> str | None:
        """Why a capability key cannot be saved, or `None` when its server needs it."""
        if not isinstance(details, CapabilityDetails):
            return None
        try:
            needs = self.mcp.needs(details.server)
        except KeyError:
            return f"no capability {details.server!r} is configured"
        if details.variable in needs:
            return None
        if not needs:
            return f"{details.server} needs no key"
        return f"{details.server} needs {', '.join(needs)}, not {details.variable}"

    async def added(self, name: str, details: CredentialDetails, bot_ids: tuple[str, ...]) -> None:
        """Start what the new credential `name` is for, or tie a website key to `bot_ids`."""
        if isinstance(details, CapabilityDetails):
            await self.restart_capabilities(details)
        elif isinstance(details, ChatPlatformDetails):
            await self.platforms.restart(details.kind)
        elif isinstance(details, CustomDetails):
            self.bots.tie_key(name, bot_ids)

    async def changed(
        self,
        name: str,
        replaced: CredentialDetails,
        details: CredentialDetails,
        *,
        bot_ids: tuple[str, ...],
        is_new_key: bool,
    ) -> None:
        """Restart what `name` was and is now for, or tie a website key to `bot_ids`."""
        if isinstance(details, CapabilityDetails):
            await self.restart_capabilities(replaced, details)
        elif isinstance(details, CustomDetails):
            self.bots.tie_key(name, bot_ids)
        elif isinstance(details, ChatPlatformDetails) and is_new_key:
            await self.platforms.restart(details.kind)

    async def removed(self, name: str, details: CredentialDetails) -> None:
        """Untie `name` from every bot, and stop or restart what it was for."""
        self.bots.forget_secret(name)
        if isinstance(details, ChatPlatformDetails):
            await self.platforms.restart(details.kind)
        await self.restart_capabilities(details)

    async def restart_capabilities(self, *held: CredentialDetails) -> None:
        """Restart, once each, every configured server one of `held` is a capability key for."""
        configured = {server.id for server in self.mcp.statuses()}
        servers = dict.fromkeys(
            details.server
            for details in held
            if isinstance(details, CapabilityDetails) and details.server in configured
        )
        for server_id in servers:
            await self.mcp.restart(server_id)
