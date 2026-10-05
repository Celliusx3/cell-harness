"""A bot's chat: read, send, stream, stop, clear."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from harness.bots import Bot, BotNotFound
from harness.channels.commands import unknown_skill
from harness.channels.protocol import InboundMessage
from harness.channels.web.schemas import ConversationDetail, MessageAccepted, SendMessage
from harness.channels.web.sse import MEDIA_TYPE, Source, kept_alive, sse_frames
from harness.session.log import Session
from harness.session.repository import (
    SessionCorruptionError,
    SessionFormatUnsupportedError,
    SessionNotFoundError,
)
from harness.session.service import SessionService
from harness.skills import UnknownSkill

if TYPE_CHECKING:
    from harness.channels.web.channel import WebChannel

logger = logging.getLogger("harness.web")


def _unknown_skill(web: WebChannel, err: UnknownSkill) -> HTTPException:
    """The `detail` for a `/word` that is neither a command nor a skill."""
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=unknown_skill(err.name, web.gateway.skills.invocable()),
    )


def _accepted(session: Session, *, queued: bool) -> MessageAccepted:
    header = session.header
    return MessageAccepted(id=header.id, created_at=header.created_at, queued=queued)


def bot_chat_router(web: WebChannel, *, tag: str) -> APIRouter:
    """A router under `/api/conversations` whose every route is a 404 for an id that is no bot's."""

    async def owning_bot(conversation_id: str) -> Bot:
        try:
            return web.bots.bot_for(conversation_id)
        except BotNotFound as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    return APIRouter(prefix="/api/conversations", tags=[tag], dependencies=[Depends(owning_bot)])


async def _load(service: SessionService, conversation_id: str, *, for_writing: bool) -> Session:
    """Fetch a stored conversation, mapping its failures onto status codes."""
    try:
        if for_writing:
            return await service.resume(conversation_id)
        return await service.read(conversation_id)
    except SessionNotFoundError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except (SessionCorruptionError, SessionFormatUnsupportedError) as err:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err)) from err


def build_router(web: WebChannel) -> APIRouter:
    """The browser's endpoints, bound to one channel."""
    router = bot_chat_router(web, tag="conversations")

    @router.get("/{conversation_id}", response_model=ConversationDetail)
    async def get_conversation(conversation_id: str) -> ConversationDetail:
        """The whole log, and the cursor to start streaming from."""
        run = web.runs.active(conversation_id)
        session = (
            run.session
            if run is not None
            else await _load(web.sessions, conversation_id, for_writing=False)
        )
        events = list(session.events())
        header = session.header
        return ConversationDetail(
            id=header.id,
            created_at=header.created_at,
            events=events,
            next_cursor=session.next_number(),
            running=run is not None,
        )

    @router.post(
        "/{conversation_id}/messages",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=MessageAccepted,
    )
    async def send_message(conversation_id: str, body: SendMessage) -> MessageAccepted:
        """Continue a conversation."""
        try:
            run = await web.gateway.receive(
                InboundMessage(channel=web.channel, chat_id=conversation_id, text=body.prompt)
            )
        except SessionNotFoundError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
        except UnknownSkill as err:
            raise _unknown_skill(web, err) from err

        if run is not None:
            return _accepted(run.session, queued=False)
        active = web.runs.active(conversation_id)
        session = (
            active.session
            if active is not None
            else await _load(web.sessions, conversation_id, for_writing=False)
        )
        return _accepted(session, queued=True)

    @router.get("/{conversation_id}/events")
    async def stream_events(conversation_id: str, after: int = Query(0, ge=0)) -> StreamingResponse:
        """Events from `after` onward as SSE, live if a turn is running."""

        async def source() -> Source:
            run = web.runs.active(conversation_id)
            if run is not None:
                return run
            return await _load(web.sessions, conversation_id, for_writing=False)

        async def after_drain() -> Source:
            await web.gateway.drained(web.channel, conversation_id)
            return await source()

        return StreamingResponse(
            kept_alive(sse_frames(await source(), after=after, after_drain=after_drain)),
            media_type=MEDIA_TYPE,
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.delete("/{conversation_id}/run", status_code=status.HTTP_204_NO_CONTENT)
    async def stop_run(conversation_id: str) -> Response:
        """Stop the turn in flight."""
        if not await web.runs.stop(conversation_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no turn is running")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{conversation_id}/clear", status_code=status.HTTP_204_NO_CONTENT)
    async def clear_chat(conversation_id: str) -> Response:
        """Clear the chat in place: its turn stops and the history starts after it."""
        await _load(web.sessions, conversation_id, for_writing=False)
        await web.gateway.clear(web.channel, conversation_id)
        logger.info("conversation %s cleared by the browser", conversation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
