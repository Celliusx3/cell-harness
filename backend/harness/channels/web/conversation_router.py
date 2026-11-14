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
    unknown_skill_reply,
)
from harness.channels.web.schemas import (
    ConversationDetail,
    MessageAccepted,
    MessageRequest,
    ModeRequest,
)
from harness.channels.web.sse import SSE_MEDIA_TYPE, Source, kept_alive, sse_frames
from harness.files import ChatFile, ChatFileService
from harness.session.domain.log import Session
from harness.skills import UnknownSkill
from harness.web.http.files import folder_file, logged_image

if TYPE_CHECKING:
    from harness.channels.web.channel import WebChannel

logger = logging.getLogger("harness.web")

UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _chunks(upload: UploadFile) -> AsyncIterator[bytes]:
    while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
        yield chunk


def chat_router(web: WebChannel, *, tag: str) -> APIRouter:
    """A router under `/api/conversations` whose every route 404s an id no bot or group has."""

    async def require_chat_members(conversation_id: str) -> ChatMembers:
        return web.runs.groups.chat_members(conversation_id)

    return APIRouter(
        prefix="/api/conversations", tags=[tag], dependencies=[Depends(require_chat_members)]
    )


def _message_accepted(session: Session, *, queued: bool) -> MessageAccepted:
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


class ConversationRouter:
    """The browser's endpoints, bound to one channel."""

    def __init__(self, web: WebChannel) -> None:
        self._web = web
        self.router: APIRouter = chat_router(web, tag="conversations")
        self._add_message_routes()
        self._add_file_routes()
        self._add_turn_routes()

    def _add_message_routes(self) -> None:
        """Reading a chat's log, and sending the chat a message."""
        self.router.add_api_route(
            "/{conversation_id}",
            self.get_conversation,
            methods=["GET"],
            response_model=ConversationDetail,
        )
        self.router.add_api_route(
            "/{conversation_id}/messages",
            self.send_message,
            methods=["POST"],
            status_code=status.HTTP_202_ACCEPTED,
            response_model=MessageAccepted,
        )

    def _add_file_routes(self) -> None:
        """The files and images a chat holds: an upload saved, a file read, an image shown."""
        self.router.add_api_route(
            "/{conversation_id}/files",
            self.upload_file,
            methods=["POST"],
            status_code=status.HTTP_201_CREATED,
            response_model=ChatFile,
        )
        self.router.add_api_route("/{conversation_id}/file", self.read_file, methods=["GET"])
        self.router.add_api_route(
            "/{conversation_id}/images/{sha256}", self.read_image, methods=["GET"]
        )

    def _add_turn_routes(self) -> None:
        """A chat's events streamed, its turn stopped, its mode switched, and the chat cleared."""
        no_content = status.HTTP_204_NO_CONTENT
        self.router.add_api_route("/{conversation_id}/events", self.stream_events, methods=["GET"])
        self.router.add_api_route(
            "/{conversation_id}/run", self.stop_run, methods=["DELETE"], status_code=no_content
        )
        self.router.add_api_route(
            "/{conversation_id}/mode",
            self.set_approval_mode,
            methods=["PUT"],
            status_code=no_content,
        )
        self.router.add_api_route(
            "/{conversation_id}/clear", self.clear_chat, methods=["POST"], status_code=no_content
        )

    async def get_conversation(self, conversation_id: str) -> ConversationDetail:
        """The whole log, and the cursor to start streaming from."""
        run = self._web.runs.active(conversation_id)
        session = await self._chat_session(conversation_id)
        events = list(session.events())
        header = session.header
        return ConversationDetail(
            id=header.id,
            created_at=header.created_at,
            events=events,
            next_cursor=session.next_number(),
            running=run is not None,
            mode=await self._web.runs.approval_mode(conversation_id),
        )

    async def send_message(self, conversation_id: str, body: MessageRequest) -> MessageAccepted:
        """Continue a conversation; `/mode` switches it instead, before any skill is looked for."""
        web = self._web
        mode = mode_command(body.prompt)
        if mode is not None:
            return await self._switch_mode_by_command(conversation_id, mode)
        files = _attached_files(web.files, conversation_id, body.files)
        try:
            run = await web.gateway.receive(
                InboundMessage(
                    channel=web.channel, chat_id=conversation_id, text=body.prompt, files=files
                )
            )
        except UnknownSkill as err:
            raise self._unknown_skill_error(err) from err

        if run is not None:
            return _message_accepted(run.session, queued=False)
        return _message_accepted(await self._chat_session(conversation_id), queued=True)

    async def upload_file(self, conversation_id: str, file: UploadFile) -> ChatFile:
        """Save one file in this chat's folder, for the next message to attach."""
        stored = await self._web.files.save(conversation_id, file.filename or "", _chunks(file))
        logger.info("conversation %s was sent %s", conversation_id, stored.path)
        return stored

    async def read_file(self, conversation_id: str, path: str) -> FileResponse:
        """A file in this chat's folder: an image shown in place, anything else downloaded."""
        return folder_file(self._web.files, conversation_id, path)

    async def read_image(self, conversation_id: str, sha256: str) -> FileResponse:
        """An image this chat's log shows the model, shown in place, by the hash it is kept by."""
        session = await self._chat_session(conversation_id)
        return logged_image(self._web.images, session.events(), sha256)

    async def stream_events(
        self, conversation_id: str, after: int = Query(0, ge=0)
    ) -> StreamingResponse:
        """Events from `after` onward as SSE, live if a turn is running."""
        web = self._web

        async def source() -> Source:
            run = web.runs.active(conversation_id)
            if run is not None:
                return run
            return await web.sessions.read(conversation_id)

        async def after_drain() -> Source:
            await web.gateway.wait_until_drained(web.channel, conversation_id)
            return await source()

        return StreamingResponse(
            kept_alive(sse_frames(await source(), after=after, after_drain=after_drain)),
            media_type=SSE_MEDIA_TYPE,
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def stop_run(self, conversation_id: str) -> Response:
        """Stop the turn in flight."""
        if not await self._web.runs.stop(conversation_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no turn is running")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def set_approval_mode(self, conversation_id: str, body: ModeRequest) -> Response:
        """Switch what asks in this chat: its next call follows `mode`."""
        await self._web.runs.set_approval_mode(conversation_id, body.mode)
        logger.info("conversation %s switched to %s by the browser", conversation_id, body.mode)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def clear_chat(self, conversation_id: str) -> Response:
        """Clear the chat in place: its turn stops and the history starts after it."""
        await self._web.sessions.read(conversation_id)
        await self._web.gateway.clear(self._web.channel, conversation_id)
        logger.info("conversation %s cleared by the browser", conversation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    def _unknown_skill_error(self, err: UnknownSkill) -> HTTPException:
        """The `detail` for a `/word` that is neither a command nor a skill."""
        return HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=unknown_skill_reply(err.name, self._web.gateway.skills.invocable()),
        )

    async def _switch_mode_by_command(
        self, conversation_id: str, command: ModeCommand
    ) -> MessageAccepted:
        """`/mode ask` or `/mode auto` switches the chat and starts no turn; any other is a 422."""
        web = self._web
        if not isinstance(command, ModeChoice):
            current = await web.runs.approval_mode(conversation_id)
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail=mode_usage_reply(current)
            )
        await web.gateway.set_approval_mode(web.channel, conversation_id, command.mode)
        logger.info("conversation %s switched to %s by /mode", conversation_id, command.mode)
        return _message_accepted(await self._chat_session(conversation_id), queued=False)

    async def _chat_session(self, conversation_id: str) -> Session:
        """The running turn's session, else the stored one, read without repair."""
        run = self._web.runs.active(conversation_id)
        if run is not None:
            return run.session
        return await self._web.sessions.read(conversation_id)
