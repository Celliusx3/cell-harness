"""One folder of a chat's workspace, for the panel beside the chat."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from harness.files.domain.models import WorkspaceListing, WorkspacePathError
from harness.files.service.file_service import ChatFileService


class WorkspaceRouter:
    """List a folder of a chat's workspace; a path outside it, or an unplain chat id, is a 404."""

    def __init__(self, files: ChatFileService) -> None:
        self._files = files
        self.router: APIRouter = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
        self.router.add_api_route(
            "/{chat_id}", self.read_listing, methods=["GET"], response_model=WorkspaceListing
        )

    def read_listing(self, chat_id: str, path: str = "") -> WorkspaceListing:
        """The folder `path` names, relative to the chat's workspace, "" for its root."""
        try:
            return self._files.listing(chat_id, path)
        except (WorkspacePathError, ValueError) as err:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(err)) from err
