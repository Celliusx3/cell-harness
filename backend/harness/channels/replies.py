"""Outbound: one turn's replies, sent as they land, behind a cursor."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from urllib.parse import quote

from harness.channels.protocol import Pushing
from harness.channels.repository import ChatRepository, ChatState
from harness.runs.store import Run
from harness.runs.subscribe import subscribe
from harness.session.compaction import CompactionEnd
from harness.session.models import AssistantMessageEvent, ToolCallEvent, ToolResultEvent
from harness.tools.client import PendingCall

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


class Replies:
    """Sends a turn's replies to the chat that asked, and remembers how far."""

    def __init__(
        self, repository: ChatRepository, *, public_url: str, client_tools: frozenset[str]
    ) -> None:
        self._repository = repository
        self._client_tools = client_tools
        self._public_url = public_url
        if not public_url:
            logger.info("web.public_url is not set; app links will not be sent to chats")

    async def deliver(self, transport: Pushing, channel: str, chat_id: str, run: Run) -> None:
        """Send this turn's replies as they land."""
        typing = asyncio.create_task(self._keep_typing(transport, chat_id))
        try:
            state = await self._state(channel, chat_id)
            cursor = state.delivered_through
            names: dict[str, str] = {}
            async for event in subscribe(run, after=cursor):
                cursor += 1
                if isinstance(event, ToolCallEvent):
                    names[event.call.id] = event.call.name
                    if event.call.name not in self._client_tools:
                        continue
                    await self._ask_client(
                        transport,
                        chat_id,
                        PendingCall(event.call.name, event.call.id, event.call.arguments),
                        answer_url(self._public_url, run.session.id, event.call.id),
                    )
                elif isinstance(event, ToolResultEvent):
                    if event.ui is None or not self._public_url:
                        continue
                    call_id = event.message.tool_call_id
                    await self._send_link(
                        transport,
                        chat_id,
                        names.get(call_id, event.ui.server),
                        app_url(self._public_url, run.session.id, call_id),
                    )
                elif isinstance(event, AssistantMessageEvent):
                    if not event.message.content.strip():
                        continue
                    await transport.send_message(chat_id, event.message.content)
                elif isinstance(event, CompactionEnd):
                    await transport.send_message(chat_id, _compaction_line(event))
                else:
                    continue
                state = await self._state(channel, chat_id)
                await self._repository.save(state.model_copy(update={"delivered_through": cursor}))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("delivery failed for %s chat %s", channel, chat_id)
        finally:
            typing.cancel()
            with contextlib.suppress(BaseException):
                await typing

    async def _state(self, channel: str, chat_id: str) -> ChatState:
        """This chat's stored state, read now."""
        stored = await self._repository.load(channel, chat_id)
        if stored is None:
            raise RuntimeError(f"{channel} chat {chat_id} has no stored state to deliver to")
        return stored

    async def _send_link(self, transport: Pushing, chat_id: str, text: str, url: str) -> None:
        """Best-effort, unlike a reply."""
        try:
            await transport.send_link(chat_id, text, url)
        except Exception:
            logger.warning("app link %s could not be sent to chat %s", url, chat_id, exc_info=True)

    async def _ask_client(
        self, transport: Pushing, chat_id: str, request: PendingCall, url: str
    ) -> None:
        """Best-effort: an unsent prompt times out into a result the model can act on."""
        try:
            await transport.ask_client(chat_id, request, url)
        except Exception:
            logger.warning("%s could not be asked of chat %s", request.name, chat_id, exc_info=True)

    async def _keep_typing(self, transport: Pushing, chat_id: str) -> None:
        """Refresh the typing indicator until cancelled."""
        while True:
            await transport.send_typing(chat_id)
            await asyncio.sleep(TYPING_INTERVAL_SECONDS)
