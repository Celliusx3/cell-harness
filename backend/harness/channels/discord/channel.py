"""Discord, whole: receiving, sending, and where it differs from Telegram."""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from harness.channels.commands import Command, unknown_skill
from harness.channels.commands import apply as apply_command
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage, OnMissing
from harness.channels.text import split_message
from harness.skills import UnknownSkill
from harness.tools.client import PendingCall

logger = logging.getLogger("harness.channels.discord")

CHANNEL = "discord"

MAX_MESSAGE_CHARS = 2000

OPEN_LABEL = "Open"
ASK_BY_LINK = "The assistant needs something from your device. Open the page to answer."
NO_ANSWER_PAGE = "(Answering from Discord needs `web.public_url` to be set.)"


class DiscordChannel:
    """`Channel` and `Pushing` for Discord: receive, send, show typing."""

    channel = CHANNEL
    on_missing: OnMissing = "recreate"

    def __init__(self, token: str, gateway: ChannelGateway) -> None:
        self._token = token
        self._gateway = gateway
        self._client = discord.Client(
            intents=discord.Intents.default(),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        # `Client.event` registers by the coroutine's `__name__`.
        self._client.event(self.on_message)
        self._tree = app_commands.CommandTree(self._client)
        self._register_commands()

    def _register_commands(self) -> None:
        """`/new` and `/stop` as the interactions API expects them."""

        @self._tree.command(name="new", description="Start a fresh conversation")
        async def new(interaction: discord.Interaction) -> None:
            await self._on_command(interaction, Command.NEW)

        @self._tree.command(name="stop", description="Stop the current reply")
        async def stop(interaction: discord.Interaction) -> None:
            await self._on_command(interaction, Command.STOP)

        @self._tree.command(name="skills", description="List the skills you can type as /name")
        async def skills(interaction: discord.Interaction) -> None:
            await self._on_command(interaction, Command.SKILLS)

        @self._tree.command(
            name="compact", description="Summarize the conversation to free up context"
        )
        async def compact(interaction: discord.Interaction) -> None:
            await self._on_command(interaction, Command.COMPACT)

    async def run(self) -> None:
        """Hold the websocket until cancelled."""
        try:
            await self._client.login(self._token)
            # discord.py needs the application id `login` fetched before `sync`.
            await self._tree.sync()
            await self._client.connect()
        finally:
            await self._client.close()

    async def on_message(self, message: discord.Message) -> None:
        """One inbound message from the gateway websocket."""
        if message.author.bot:
            return
        if message.guild is not None and not self._mentions_me(message):
            return
        text = self._strip_mention(message.content).strip()
        if not text:
            return
        chat_id = str(message.channel.id)
        try:
            await self._gateway.receive(InboundMessage(channel=CHANNEL, chat_id=chat_id, text=text))
        except UnknownSkill as err:
            await self.send_message(
                chat_id, unknown_skill(err.name, self._gateway.skills.invocable())
            )
        except Exception:
            logger.exception("handling message from chat %s failed", chat_id)

    def _mentions_me(self, message: discord.Message) -> bool:
        me = self._client.user
        return me is not None and any(user.id == me.id for user in message.mentions)

    def _strip_mention(self, content: str) -> str:
        me = self._client.user
        if me is None:
            return content
        # `<@!id>` is the legacy nickname form; clients still send it.
        return content.replace(f"<@{me.id}>", "").replace(f"<@!{me.id}>", "")

    async def _on_command(self, interaction: discord.Interaction, command: Command) -> None:
        """One slash command."""
        await interaction.response.defer()
        reply = await apply_command(self._gateway, CHANNEL, str(interaction.channel_id), command)
        await interaction.followup.send(reply)

    async def send_message(self, chat_id: str, text: str) -> None:
        """Send `text`, split across messages if it exceeds the limit."""
        target = await self._messageable(chat_id)
        for part in split_message(text, MAX_MESSAGE_CHARS):
            if part:
                await target.send(part)

    async def send_link(self, chat_id: str, text: str, url: str) -> None:
        """One message with one link button."""
        view = discord.ui.View()
        view.add_item(discord.ui.Button(style=discord.ButtonStyle.link, label=OPEN_LABEL, url=url))
        target = await self._messageable(chat_id)
        await target.send(text, view=view)

    async def ask_client(self, chat_id: str, _request: PendingCall, url: str) -> None:
        """The page that asks the browser, whatever the tool — see `ASK_BY_LINK`."""
        if not url:
            await self.send_message(chat_id, f"{ASK_BY_LINK} {NO_ANSWER_PAGE}")
            return
        await self.send_link(chat_id, ASK_BY_LINK, url)

    async def send_typing(self, chat_id: str) -> None:
        """Show "typing…" for about ten seconds. Best-effort by contract."""
        try:
            target = await self._messageable(chat_id)
            await target.typing()
        except discord.HTTPException as err:
            logger.debug("typing indicator failed for chat %s: %s", chat_id, err)

    async def _messageable(self, chat_id: str) -> discord.abc.Messageable:
        """The DM, channel or thread behind a chat id."""
        cached = self._client.get_channel(int(chat_id))
        if cached is not None:
            return cached
        return await self._client.fetch_channel(int(chat_id))
