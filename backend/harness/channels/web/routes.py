"""Conversations: list, read, send, stream, stop."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from harness.channels.commands import unknown_skill
from harness.channels.protocol import InboundMessage
from harness.channels.web.schemas import (
    ConversationDetail,
    ConversationSummary,
    MessageAccepted,
    SendMessage,
)
from harness.channels.web.sse import MEDIA_TYPE, Source, sse_frames
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


def _unknown_skill(web: WebChannel, err: UnknownSkill) -> HTTPException:
    """The `detail` for a `/word` that is neither a command nor a skill."""
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=unknown_skill(err.name, web.gateway.skills.invocable()),
    )


def _summary(session: Session) -> ConversationSummary:
    header = session.header
    return ConversationSummary(id=header.id, created_at=header.created_at, title=header.title)


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
    router = APIRouter(prefix="/api/conversations", tags=["conversations"])

    @router.get("", response_model=list[ConversationSummary])
    async def list_conversations() -> list[ConversationSummary]:
        """Every stored conversation, newest first."""
        return [
            ConversationSummary(id=h.id, created_at=h.created_at, title=h.title)
            for h in await web.sessions.list()
        ]

    @router.post("", status_code=status.HTTP_201_CREATED, response_model=ConversationSummary)
    async def create_conversation(body: SendMessage) -> ConversationSummary:
        """Start a new conversation with its first message."""
        session = await web.sessions.create()
        try:
            await web.gateway.start_turn(session, body.prompt, channel=web.channel)
        except UnknownSkill as err:
            raise _unknown_skill(web, err) from err
        return _summary(session)

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
            title=header.title,
            events=events,
            next_cursor=len(events),
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
            return MessageAccepted(**_summary(run.session).model_dump(), queued=False)
        active = web.runs.active(conversation_id)
        session = (
            active.session
            if active is not None
            else await _load(web.sessions, conversation_id, for_writing=False)
        )
        return MessageAccepted(**_summary(session).model_dump(), queued=True)

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
            sse_frames(await source(), after=after, after_drain=after_drain),
            media_type=MEDIA_TYPE,
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.delete("/{conversation_id}/run", status_code=status.HTTP_204_NO_CONTENT)
    async def stop_run(conversation_id: str) -> Response:
        """Stop the turn in flight."""
        if not await web.runs.stop(conversation_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no turn is running")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
