"""A bot's or a group's chat: read, send, stream, stop, clear, and the files and images it holds."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from harness.bots import ChatMembers
from harness.channels.domain.protocol import InboundMessage
from harness.channels.service.commands import (
    ModeChoice,
    ModeCommand,
    mode_command,
    mode_usage_reply,
    unknown_skill,
)
from harness.channels.web.schemas import ConversationDetail, MessageAccepted, SendMessage, SetMode
from harness.channels.web.sse import MEDIA_TYPE, Source, kept_alive, sse_frames
from harness.files import ChatFile, ChatFileService
from harness.session.domain.log import Session
from harness.session.service.session_service import SessionService
from harness.skills import UnknownSkill
from harness.web.http.files import folder_file, logged_image

if TYPE_CHECKING:
    from harness.channels.web.channel import WebChannel

logger = logging.getLogger("harness.web")

UPLOAD_CHUNK_BYTES = 1024 * 1024


def _unknown_skill(web: WebChannel, err: UnknownSkill) -> HTTPException:
    """The `detail` for a `/word` that is neither a command nor a skill."""
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=unknown_skill(err.name, web.gateway.skills.invocable()),
    )


def _accepted(session: Session, *, queued: bool) -> MessageAccepted:
    header = session.header
    return MessageAccepted(id=header.id, created_at=header.created_at, queued=queued)


async def _switch_by_command(
    web: WebChannel, conversation_id: str, command: ModeCommand
) -> MessageAccepted:
    """`/mode ask` or `/mode auto` switches the chat and starts no turn; any other is a 422."""
    if not isinstance(command, ModeChoice):
        current = await web.runs.approval_mode(conversation_id)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=mode_usage_reply(current))
    await web.gateway.set_approval_mode(web.channel, conversation_id, command.mode)
    logger.info("conversation %s switched to %s by /mode", conversation_id, command.mode)
    return _accepted(await _chat_session(web, conversation_id), queued=False)


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
        return web.runs.groups.members_of_chat(conversation_id)

    return APIRouter(prefix="/api/conversations", tags=[tag], dependencies=[Depends(answering)])


async def _load(service: SessionService, conversation_id: str, *, for_writing: bool) -> Session:
    """Fetch a stored conversation, repaired first when it is to be written to."""
    if for_writing:
        return await service.resume(conversation_id)
    return await service.read(conversation_id)


async def _chat_session(web: WebChannel, conversation_id: str) -> Session:
    """The running turn's session, else the stored one, read without repair."""
    run = web.runs.active(conversation_id)
    if run is not None:
        return run.session
    return await _load(web.sessions, conversation_id, for_writing=False)


def _message_routes(router: APIRouter, web: WebChannel) -> None:
    """Reading a chat's log, and sending the chat a message."""

    @router.get("/{conversation_id}", response_model=ConversationDetail)
    async def get_conversation(conversation_id: str) -> ConversationDetail:
        """The whole log, and the cursor to start streaming from."""
        run = web.runs.active(conversation_id)
        session = await _chat_session(web, conversation_id)
        events = list(session.events())
        header = session.header
        return ConversationDetail(
            id=header.id,
            created_at=header.created_at,
            events=events,
            next_cursor=session.next_number(),
            running=run is not None,
            mode=await web.runs.approval_mode(conversation_id),
        )

    @router.post(
        "/{conversation_id}/messages",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=MessageAccepted,
    )
    async def send_message(conversation_id: str, body: SendMessage) -> MessageAccepted:
        """Continue a conversation; `/mode` switches it instead, before any skill is looked for."""
        mode = mode_command(body.prompt)
        if mode is not None:
            return await _switch_by_command(web, conversation_id, mode)
        files = _attached_files(web.files, conversation_id, body.files)
        try:
            run = await web.gateway.receive(
                InboundMessage(
                    channel=web.channel, chat_id=conversation_id, text=body.prompt, files=files
                )
            )
        except UnknownSkill as err:
            raise _unknown_skill(web, err) from err

        if run is not None:
            return _accepted(run.session, queued=False)
        return _accepted(await _chat_session(web, conversation_id), queued=True)


def _file_routes(router: APIRouter, web: WebChannel) -> None:
    """The files and images a chat holds: an upload saved, a file read, an image shown."""

    @router.post(
        "/{conversation_id}/files",
        status_code=status.HTTP_201_CREATED,
        response_model=ChatFile,
    )
    async def upload_file(conversation_id: str, file: UploadFile) -> ChatFile:
        """Save one file in this chat's folder, for the next message to attach."""
        stored = await web.files.save(conversation_id, file.filename or "", _chunks(file))
        logger.info("conversation %s was sent %s", conversation_id, stored.path)
        return stored

    @router.get("/{conversation_id}/file")
    async def read_file(conversation_id: str, path: str) -> FileResponse:
        """A file in this chat's folder: an image shown in place, anything else downloaded."""
        return folder_file(web.files, conversation_id, path)

    @router.get("/{conversation_id}/images/{sha256}")
    async def read_image(conversation_id: str, sha256: str) -> FileResponse:
        """An image this chat's log shows the model, shown in place, by the hash it is kept by."""
        session = await _chat_session(web, conversation_id)
        return logged_image(web.images, session.events(), sha256)


def _turn_routes(router: APIRouter, web: WebChannel) -> None:
    """A chat's events streamed, its turn stopped, its mode switched, and the chat cleared."""

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

    @router.put("/{conversation_id}/mode", status_code=status.HTTP_204_NO_CONTENT)
    async def set_approval_mode(conversation_id: str, body: SetMode) -> Response:
        """Switch what asks in this chat: its next call follows `mode`."""
        await web.runs.set_approval_mode(conversation_id, body.mode)
        logger.info("conversation %s switched to %s by the browser", conversation_id, body.mode)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{conversation_id}/clear", status_code=status.HTTP_204_NO_CONTENT)
    async def clear_chat(conversation_id: str) -> Response:
        """Clear the chat in place: its turn stops and the history starts after it."""
        await _load(web.sessions, conversation_id, for_writing=False)
        await web.gateway.clear(web.channel, conversation_id)
        logger.info("conversation %s cleared by the browser", conversation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


def build_router(web: WebChannel) -> APIRouter:
    """The browser's endpoints, bound to one channel."""
    router = chat_router(web, tag="conversations")
    _message_routes(router, web)
    _file_routes(router, web)
    _turn_routes(router, web)
    return router
