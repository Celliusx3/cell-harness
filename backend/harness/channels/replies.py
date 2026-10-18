"""Outbound: one turn's replies, sent as they land."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import NamedTuple
from urllib.parse import quote

from harness.channels.protocol import Pushing
from harness.channels.repository import ChatRepository
from harness.runs.service import Run
from harness.runs.subscribe import subscribe
from harness.session.compaction import CompactionEnd
from harness.session.models import AssistantMessageEvent, ToolCallEvent, ToolResultEvent, TurnEnd
from harness.tools.client import PendingCall, next_pending

logger = logging.getLogger("harness.channels")

# Telegram clears its typing indicator after ~5s and Discord after ~10.
TYPING_INTERVAL_SECONDS = 4.0


def app_url(public_url: str, conversation_id: str, call_id: str) -> str:
    """The page that renders one tool call's MCP App — `frontend/app/apps/`."""
    return f"{public_url}/apps/{quote(conversation_id, safe='')}/{quote(call_id, safe='')}"


def answer_url(public_url: str, conversation_id: str, call_id: str) -> str:
    """The page that answers one client-tool call — `frontend/app/answer/`."""
    if not public_url:
        return ""
    return f"{public_url}/answer/{quote(conversation_id, safe='')}/{quote(call_id, safe='')}"


def _compaction_line(event: CompactionEnd) -> str:
    """What a chat is told when a manual compaction settles."""
    if event.succeeded:
        return "Conversation compacted to free up context."
    return "Could not compact the conversation right now."


class _AppLink(NamedTuple):
    """What a chat is sent for a result drawn with an MCP App."""

    text: str
    url: str


class Replies:
    """Sends a turn's replies to the chat that asked, and remembers what it was asked."""

    def __init__(self, repository: ChatRepository, *, public_url: str) -> None:
        self._repository = repository
        self._public_url = public_url
        if not public_url:
            logger.info("web.public_url is not set; app links will not be sent to chats")

    async def deliver(self, transport: Pushing, channel: str, chat_id: str, run: Run) -> None:
        """Send this turn's replies as they land."""
        typing = asyncio.create_task(self._keep_typing(transport, chat_id))
        try:
            names: dict[str, str] = {}
            pending: tuple[PendingCall, ...] = ()
            async for item in subscribe(run, after=run.first_event_number):
                event = item.event
                pending = next_pending(pending, event)
                if isinstance(event, ToolCallEvent):
                    names[event.call.id] = event.call.name
                elif isinstance(event, ToolResultEvent):
                    link = self._app_link(event, names, run.session.id)
                    await self._send_link(transport, chat_id, link)
                elif isinstance(event, AssistantMessageEvent):
                    await self._send_reply(transport, chat_id, event.message.content)
                elif isinstance(event, CompactionEnd):
                    await transport.send_message(chat_id, _compaction_line(event))
                elif isinstance(event, TurnEnd) and event.reason == "pending":
                    await self._remember_asked(channel, chat_id, pending)
                    await self._ask_each(transport, chat_id, run.session.id, pending)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("delivery failed for %s chat %s", channel, chat_id)
        finally:
            typing.cancel()
            with contextlib.suppress(BaseException):
                await typing

    async def _remember_asked(
        self, channel: str, chat_id: str, calls: tuple[PendingCall, ...]
    ) -> None:
        """Record the calls this chat was asked."""
        stored = await self._repository.load(channel, chat_id)
        if stored is None:
            raise RuntimeError(f"{channel} chat {chat_id} has no stored state to be asked in")
        new = tuple(call.call_id for call in calls if call.call_id not in stored.asked)
        await self._repository.save(stored.model_copy(update={"asked": (*stored.asked, *new)}))

    def _app_link(
        self, event: ToolResultEvent, names: dict[str, str], session_id: str
    ) -> _AppLink | None:
        """The link to a result's MCP App; none without an app or a public URL to reach it."""
        if event.ui is None or not self._public_url:
            return None
        call_id = event.message.tool_call_id
        return _AppLink(
            names.get(call_id, event.ui.server),
            app_url(self._public_url, session_id, call_id),
        )

    async def _send_link(self, transport: Pushing, chat_id: str, link: _AppLink | None) -> None:
        """Best-effort, unlike a reply."""
        if link is None:
            return
        try:
            await transport.send_link(chat_id, link.text, link.url)
        except Exception:
            logger.warning(
                "app link %s could not be sent to chat %s", link.url, chat_id, exc_info=True
            )

    async def _send_reply(self, transport: Pushing, chat_id: str, text: str) -> None:
        """Send what the model said, unless it said nothing."""
        if not text.strip():
            return
        await transport.send_message(chat_id, text)

    async def _ask_each(
        self, transport: Pushing, chat_id: str, session_id: str, calls: tuple[PendingCall, ...]
    ) -> None:
        """Best-effort: an unsent prompt times out into a result the model can act on."""
        for call in calls:
            url = answer_url(self._public_url, session_id, call.call_id)
            try:
                await transport.ask_client(chat_id, call, url)
            except Exception:
                logger.warning(
                    "%s could not be asked of chat %s", call.name, chat_id, exc_info=True
                )

    async def _keep_typing(self, transport: Pushing, chat_id: str) -> None:
        """Refresh the typing indicator until cancelled."""
        while True:
            await transport.send_typing(chat_id)
            await asyncio.sleep(TYPING_INTERVAL_SECONDS)
