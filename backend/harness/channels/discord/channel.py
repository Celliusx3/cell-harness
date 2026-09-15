"""Discord, whole: receiving, sending, and where it differs from Telegram.

**Who it answers.** Every DM, and a guild channel or thread message only when
the bot is `@mentioned`. That is what `hermes-agent` (`require_mention`,
default on) and OpenClaw (`requireMention`, default on) both do, and it is also
what makes the privileged *Message Content* intent unnecessary: Discord exempts
DMs and messages that mention the bot from it, so the bot reads exactly what is
addressed to it and structurally nothing else — no Developer Portal toggle, and
no server whose whole traffic is fed to a model. Hermes's auto-thread on mention
is the one thing this deliberately leaves out, because un-mentioned messages in
that thread would need the intent.

**One conversation per DM, channel or thread.** A thread has its own id, so
opening one is Discord's own idiom for "new conversation"; `/new` is for when
someone wants a fresh start in the same place.

**Why `discord.py`.** For the same reasons `python-telegram-bot` is here: it
owns the gateway websocket, heartbeats and reconnects, bucket-aware `429`
handling, and the interactions wire that slash commands arrive on. `Client.run()`
is not used — it installs signal handlers and owns the loop, which this server
already does — so `run()` below is the two calls `start()` is made of.

**No inbound batching.** Telegram's client splits a long paste into several
messages; Discord's refuses to send one over 2000 characters, so nothing arrives
in pieces. A message during a turn is queued by the gateway like anywhere else.

**Bots are ignored, the bot itself included.** Discord delivers the bot's own
sends back through `on_message`, and two bots answering each other never stop —
by "dedupe by consequence" (`channels/__init__.py`) that is the kind of thing
that earns a guard.
"""

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

logger = logging.getLogger("harness.channels.discord")

CHANNEL = "discord"

# Discord's hard cap on one message. The library fails the send rather than
# splitting, and our own rules forbid truncating anything user-facing.
MAX_MESSAGE_CHARS = 2000

# The button under a message that links to an MCP App's page.
OPEN_LABEL = "Open"


class DiscordChannel:
    """`Channel` and `Pushing` for Discord: receive, send, show typing."""

    channel = CHANNEL
    # Same as Telegram: the person in the chat has no address bar to correct.
    on_missing: OnMissing = "recreate"

    def __init__(self, token: str, gateway: ChannelGateway) -> None:
        self._token = token
        self._gateway = gateway
        self._client = discord.Client(
            # The default set carries guild and DM messages; `message_content`
            # stays off on purpose — see the module docstring.
            intents=discord.Intents.default(),
            # A model that writes `@everyone` must not be able to ping a server.
            allowed_mentions=discord.AllowedMentions.none(),
        )
        # `Client.event` registers by the coroutine's `__name__`.
        self._client.event(self.on_message)
        self._tree = app_commands.CommandTree(self._client)
        self._register_commands()

    def _register_commands(self) -> None:
        """`/new` and `/stop` as the interactions API expects them.

        Closures rather than decorated methods, because the tree reads the
        callback's signature and wants exactly one `Interaction` parameter.
        """

        @self._tree.command(name="new", description="Start a fresh conversation")
        async def new(interaction: discord.Interaction) -> None:
            await self._on_command(interaction, Command.NEW)

        @self._tree.command(name="stop", description="Stop the current reply")
        async def stop(interaction: discord.Interaction) -> None:
            await self._on_command(interaction, Command.STOP)

        @self._tree.command(name="skills", description="List the skills you can type as /name")
        async def skills(interaction: discord.Interaction) -> None:
            await self._on_command(interaction, Command.SKILLS)

    # ── receiving ─────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Hold the websocket until cancelled."""
        try:
            await self._client.login(self._token)
            # Global, on every start: one bulk overwrite, which the library's
            # rate limiting absorbs even under `--reload`. Needs the application
            # id, which `login` fetched.
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
            # A bare ping is not a prompt.
            return
        chat_id = str(message.channel.id)
        try:
            await self._gateway.receive(InboundMessage(channel=CHANNEL, chat_id=chat_id, text=text))
        except UnknownSkill as err:
            await self.send_message(
                chat_id, unknown_skill(err.name, self._gateway.skills.invocable())
            )
        except Exception:
            # One chat's bad message is not a reason to stop answering everyone
            # else, and the library would otherwise route this to `on_error`.
            logger.exception("handling message from chat %s failed", chat_id)

    def _mentions_me(self, message: discord.Message) -> bool:
        # A reply to the bot's message pings it too, and that counts: replying
        # is how someone continues a conversation in a busy channel.
        me = self._client.user
        return me is not None and any(user.id == me.id for user in message.mentions)

    def _strip_mention(self, content: str) -> str:
        me = self._client.user
        if me is None:
            return content
        # `<@!id>` is the legacy nickname form; clients still send it.
        return content.replace(f"<@{me.id}>", "").replace(f"<@!{me.id}>", "")

    async def _on_command(self, interaction: discord.Interaction, command: Command) -> None:
        """One slash command. The channel it was typed in is the chat.

        Deferred first: an interaction must be acknowledged within three
        seconds, and `/stop` waits for the cancelled turn to settle on disk.
        """
        await interaction.response.defer()
        reply = await apply_command(self._gateway, CHANNEL, str(interaction.channel_id), command)
        await interaction.followup.send(reply)

    # ── sending ───────────────────────────────────────────────────────────────

    async def send_message(self, chat_id: str, text: str) -> None:
        """Send `text`, split across messages if it exceeds the limit.

        Markdown as the model wrote it: Discord renders it natively. A split
        inside a code fence renders broken, accepted the way Telegram accepts an
        unrendered asterisk.
        """
        target = await self._messageable(chat_id)
        for part in split_message(text, MAX_MESSAGE_CHARS):
            if part:
                await target.send(part)

    async def send_link(self, chat_id: str, text: str, url: str) -> None:
        """One message with one link button. Discord has no in-app webview, so
        the button opens the page in the browser — which suits an MCP App: the
        page is the same one the browser chat links to."""
        view = discord.ui.View()
        view.add_item(discord.ui.Button(style=discord.ButtonStyle.link, label=OPEN_LABEL, url=url))
        target = await self._messageable(chat_id)
        await target.send(text, view=view)

    async def send_typing(self, chat_id: str) -> None:
        """Show "typing…" for about ten seconds. Best-effort by contract."""
        try:
            target = await self._messageable(chat_id)
            await target.typing()
        except discord.HTTPException as err:
            logger.debug("typing indicator failed for chat %s: %s", chat_id, err)

    async def _messageable(self, chat_id: str) -> discord.abc.Messageable:
        """The DM, channel or thread behind a chat id.

        Cache first, then the API: after a restart nothing is cached, and a
        reply the gateway's cursor says is still owed must reach a chat the
        process has not heard from since.
        """
        cached = self._client.get_channel(int(chat_id))
        if cached is not None:
            return cached  # type: ignore[return-value]
        return await self._client.fetch_channel(int(chat_id))  # type: ignore[return-value]
