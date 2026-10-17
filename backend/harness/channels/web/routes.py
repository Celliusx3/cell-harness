"""A bot's or a group's chat: read, send, stream, stop, clear, and the files it holds."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from harness.bots import BotNotFound, ChatMembers, GroupEmpty
from harness.channels.commands import unknown_skill
from harness.channels.protocol import InboundMessage
from harness.channels.web.schemas import ConversationDetail, MessageAccepted, SendMessage
from harness.channels.web.sse import MEDIA_TYPE, Source, kept_alive, sse_frames
from harness.files import ChatFile, ChatFileService, FileTooLarge, UnsafeFileName
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

UPLOAD_CHUNK_BYTES = 1024 * 1024
INLINE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
NO_SNIFFING = {"X-Content-Type-Options": "nosniff"}


def _unknown_skill(web: WebChannel, err: UnknownSkill) -> HTTPException:
    """The `detail` for a `/word` that is neither a command nor a skill."""
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=unknown_skill(err.name, web.gateway.skills.invocable()),
    )


def _accepted(session: Session, *, queued: bool) -> MessageAccepted:
    header = session.header
    return MessageAccepted(id=header.id, created_at=header.created_at, queued=queued)


def _attached_files(files: ChatFileService, chat_id: str, paths: list[str]) -> tuple[ChatFile, ...]:
    """Each sent path as the file on disk; a 422 naming the first that is not one in this chat."""
    attached: list[ChatFile] = []
    for path in paths:
        stored = files.file_at(chat_id, path)
        if stored is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"{path} is not a file in this chat"
            )
        attached.append(stored)
    return tuple(attached)


async def _chunks(upload: UploadFile) -> AsyncIterator[bytes]:
    while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
        yield chunk


def chat_router(web: WebChannel, *, tag: str) -> APIRouter:
    """A router under `/api/conversations` whose every route 404s an id no bot or group has."""

    async def answering(conversation_id: str) -> ChatMembers:
        try:
            return web.bots.members_of_chat(conversation_id)
        except BotNotFound as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    return APIRouter(prefix="/api/conversations", tags=[tag], dependencies=[Depends(answering)])


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
    router = chat_router(web, tag="conversations")

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
        files = _attached_files(web.files, conversation_id, body.files)
        try:
            run = await web.gateway.receive(
                InboundMessage(
                    channel=web.channel, chat_id=conversation_id, text=body.prompt, files=files
                )
            )
        except SessionNotFoundError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
        except UnknownSkill as err:
            raise _unknown_skill(web, err) from err
        except GroupEmpty as err:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=str(err)) from err

        if run is not None:
            return _accepted(run.session, queued=False)
        active = web.runs.active(conversation_id)
        session = (
            active.session
            if active is not None
            else await _load(web.sessions, conversation_id, for_writing=False)
        )
        return _accepted(session, queued=True)

    @router.post(
        "/{conversation_id}/files",
        status_code=status.HTTP_201_CREATED,
        response_model=ChatFile,
    )
    async def upload_file(conversation_id: str, file: UploadFile) -> ChatFile:
        """Save one file in this chat's folder, for the next message to attach."""
        try:
            stored = await web.files.save(conversation_id, file.filename or "", _chunks(file))
        except UnsafeFileName as err:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)) from err
        except FileTooLarge as err:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(err)) from err
        logger.info("conversation %s was sent %s", conversation_id, stored.path)
        return stored

    @router.get("/{conversation_id}/file")
    async def read_file(conversation_id: str, path: str) -> FileResponse:
        """A file in this chat's folder: an image shown in place, anything else downloaded."""
        stored = web.files.file_at(conversation_id, path)
        if stored is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail=f"{path} is not a file here", headers=NO_SNIFFING
            )
        shown = "inline" if stored.media_type in INLINE_TYPES else "attachment"
        return FileResponse(
            stored.path,
            media_type=stored.media_type,
            filename=stored.name,
            content_disposition_type=shown,
            headers=NO_SNIFFING,
        )

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
