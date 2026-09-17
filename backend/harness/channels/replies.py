"""Outbound: one turn's replies, sent as they land, behind a cursor.

The cursor is `ChatState.delivered_through`, advanced only after a send
returns — so a restart mid-send re-sends one message rather than losing one,
and of the two a duplicate is the recoverable one. A tool result bound to an
MCP App is the one thing besides prose a chat is told about: it cannot render
the app, but it can open the page that does.
"""

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

# Telegram clears its typing indicator after ~5s and Discord after ~10, so this
# is a heartbeat rather than a state with an off switch.
TYPING_INTERVAL_SECONDS = 4.0


def app_url(public_url: str, conversation_id: str, call_id: str) -> str:
    """The page that renders one tool call's MCP App — `frontend/app/apps/`."""
    return f"{public_url}/apps/{quote(conversation_id, safe='')}/{quote(call_id, safe='')}"


def answer_url(public_url: str, conversation_id: str, call_id: str) -> str:
    """The page that answers one client-tool call — `frontend/app/answer/`.
    Empty when there is no public URL: the platform says so in words."""
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
        # The calls a chat is *asked* about before their result: the result is
        # the person's to give. Names, because that is all the log carries.
        self._client_tools = client_tools
        # Where a link to an MCP App's page points — `settings.web.public_url`.
        # Empty means no link is sent: there is nowhere a phone could open.
        self._public_url = public_url
        if not public_url:
            logger.info("web.public_url is not set; app links will not be sent to chats")

    async def deliver(self, transport: Pushing, channel: str, chat_id: str, run: Run) -> None:
        """Send this turn's replies as they land."""
        typing = asyncio.create_task(self._keep_typing(transport, chat_id))
        try:
            state = await self._state(channel, chat_id)
            cursor = state.delivered_through
            # Which tool each call was, so the link to its app can say.
            names: dict[str, str] = {}
            async for event in subscribe(run, after=cursor):
                cursor += 1
                if isinstance(event, ToolCallEvent):
                    names[event.call.id] = event.call.name
                    if event.call.name not in self._client_tools:
                        continue
                    # An ask is a delivery like any other, and the cursor
                    # must move past it below: the turn ends pending right
                    # after, and the turn that carries the answer is followed
                    # from this cursor — a stale one replays the ask.
                    await self._ask_client(
                        transport,
                        chat_id,
                        PendingCall(event.call.name, event.call.id, event.call.arguments),
                        answer_url(self._public_url, run.session.id, event.call.id),
                    )
                elif isinstance(event, ToolResultEvent):
                    # A result with an app is the one thing besides prose a chat
                    # is told about: it cannot render the app, but it can open
                    # the page that does.
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
                    # A tool-calling step records an assistant message with empty
                    # content — the model asked for a tool and said nothing.
                    # Sending an empty message is an error.
                    if not event.message.content.strip():
                        continue
                    await transport.send_message(chat_id, event.message.content)
                elif isinstance(event, CompactionEnd):
                    # A manual compaction's whole reply: the phone cannot show
                    # the summary card, but it can say it happened, or why not.
                    await transport.send_message(chat_id, _compaction_line(event))
                else:
                    continue
                # Advanced only after the send returns. A crash before this
                # re-sends one message, a crash after sends none — and of the
                # two, a duplicate is the recoverable one.
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
        """Read again before every save, so a `pending` that arrived mid-send is
        not overwritten by the copy this loop started with."""
        stored = await self._repository.load(channel, chat_id)
        if stored is None:
            # The gateway saves a chat before it begins its turn, so an absent
            # one is a wiring mistake — not a chat we have not seen.
            raise RuntimeError(f"{channel} chat {chat_id} has no stored state to deliver to")
        return stored

    async def _send_link(self, transport: Pushing, chat_id: str, text: str, url: str) -> None:
        """Best-effort, unlike a reply. A platform may refuse the URL — Telegram
        rejects `localhost` outright — and a link nobody can open is a smaller
        loss than every reply after it: raising here would abort delivery with
        the cursor unadvanced, and the next turn would replay the same event
        into the same refusal, forever."""
        try:
            await transport.send_link(chat_id, text, url)
        except Exception:
            logger.warning("app link %s could not be sent to chat %s", url, chat_id, exc_info=True)

    async def _ask_client(
        self, transport: Pushing, chat_id: str, request: PendingCall, url: str
    ) -> None:
        """Best-effort for the same reason as a link: a prompt that could not
        be sent times out into a result the model can act on, and aborting
        delivery would replay the ask into the same refusal forever."""
        try:
            await transport.ask_client(chat_id, request, url)
        except Exception:
            logger.warning("%s could not be asked of chat %s", request.name, chat_id, exc_info=True)

    async def _keep_typing(self, transport: Pushing, chat_id: str) -> None:
        """Refresh the typing indicator until cancelled."""
        while True:
            await transport.send_typing(chat_id)
            await asyncio.sleep(TYPING_INTERVAL_SECONDS)
