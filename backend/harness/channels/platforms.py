"""Telegram and Discord on the gateway while the keyring holds a token, restarted as it changes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import assert_never, get_args

from pydantic import SecretStr

from harness.channels.client import ChatAnswers
from harness.channels.discord.channel import DiscordChannel
from harness.channels.gateway import ChannelGateway
from harness.channels.links import ChatLinks
from harness.channels.protocol import Channel, ChannelDisposer
from harness.channels.telegram.channel import TelegramChannel
from harness.secrets import SecretService
from harness.secrets.models.details import ChatPlatform

CHAT_PLATFORMS: tuple[ChatPlatform, ...] = get_args(ChatPlatform)

PlatformChannelMaker = Callable[[ChatPlatform, SecretStr], Channel]


class PlatformChannels:
    """One channel per chat platform whose token the keyring holds, replaced when it changes."""

    def __init__(
        self, gateway: ChannelGateway, keyring: SecretService, make_channel: PlatformChannelMaker
    ) -> None:
        self._gateway = gateway
        self._keyring = keyring
        self._make_channel = make_channel
        self._disposers: dict[ChatPlatform, ChannelDisposer] = {}
        self._changing = asyncio.Lock()

    async def start_saved(self) -> None:
        """Register a channel for each platform whose token is saved."""
        for platform in CHAT_PLATFORMS:
            await self.restart(platform)

    async def restart(self, platform: ChatPlatform) -> None:
        """Stop `platform`'s channel, then register a fresh one if its token is saved."""
        async with self._changing:
            dispose = self._disposers.pop(platform, None)
            if dispose is not None:
                await dispose()
            token = await asyncio.to_thread(self._keyring.chat_platform_token, platform)
            if token is not None:
                channel = self._make_channel(platform, token)
                self._disposers[platform] = self._gateway.register(channel)


@dataclass(frozen=True)
class PlatformChats:
    """What a Telegram or Discord chat reaches: the gateway, its answers, and the link codes."""

    gateway: ChannelGateway
    answers: ChatAnswers
    links: ChatLinks


def platform_channel(chats: PlatformChats, platform: ChatPlatform, token: SecretStr) -> Channel:
    """The Telegram or Discord channel on `chats.gateway` that `token` signs in."""
    match platform:
        case "telegram":
            return TelegramChannel(
                token.get_secret_value(), chats.gateway, chats.answers, chats.links
            )
        case "discord":
            return DiscordChannel(token.get_secret_value(), chats.gateway, chats.links)
        case _:
            assert_never(platform)
