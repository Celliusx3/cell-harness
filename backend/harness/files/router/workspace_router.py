"""One folder of a chat's workspace, and its changes, for the panel beside the chat."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import aclosing

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from harness.channels.web.sse import SSE_MEDIA_TYPE, frame, kept_alive
from harness.files.domain.models import WorkspaceEvent, WorkspaceListing, WorkspacePathError
from harness.files.service.file_service import ChatFileService


async def _frames(events: AsyncGenerator[WorkspaceEvent]) -> AsyncGenerator[str]:
    """Each event as an SSE frame; closing the frames closes the events."""
    async with aclosing(events) as watched:
        async for event in watched:
            yield frame(event.type, event.model_dump_json())


class WorkspaceRouter:
    """List, watch or delete in a chat's workspace; a path out of it, or an unplain id, is a 404."""

    def __init__(self, files: ChatFileService) -> None:
        self._files = files
        self.router: APIRouter = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
        self.router.add_api_route(
            "/{chat_id}", self.read_listing, methods=["GET"], response_model=WorkspaceListing
        )
        self.router.add_api_route("/{chat_id}/changes", self.stream_changes, methods=["GET"])
        self.router.add_api_route(
            "/{chat_id}",
            self.delete_entry,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
        )

    def read_listing(self, chat_id: str, path: str = "") -> WorkspaceListing:
        """The folder `path` names, relative to the chat's workspace, "" for its root."""
        try:
            return self._files.listing(chat_id, path)
        except (WorkspacePathError, ValueError) as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    def stream_changes(self, chat_id: str) -> StreamingResponse:
        """Each folder of the chat's workspace that changes, while the reader stays."""
        try:
            events = self._files.changes(chat_id)
        except ValueError as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
        return StreamingResponse(
            kept_alive(_frames(events)),
            media_type=SSE_MEDIA_TYPE,
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def delete_entry(self, chat_id: str, path: str) -> None:
        """Delete the file, folder or link `path` names, relative to the chat's workspace."""
        try:
            self._files.delete_path(chat_id, path)
        except (WorkspacePathError, ValueError) as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
