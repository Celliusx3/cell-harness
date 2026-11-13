"""The files in a ticket's worker folder and the images its worker's log shows, for its page."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from harness.files import ChatFileService
from harness.images import ImageService
from harness.tickets.service.ticket_service import TicketService
from harness.tickets.service.worker import worker_session_id
from harness.web.http.files import folder_file, logged_image


def build_files_router(
    tickets: TicketService, files: ChatFileService, images: ImageService
) -> APIRouter:
    """Read a file from a ticket's worker folder, and an image its worker's log shows."""
    router = APIRouter(prefix="/api/tickets", tags=["tickets"])

    @router.get("/{ticket_id}/file")
    async def read_ticket_file(ticket_id: str, path: str) -> FileResponse:
        tickets.get(ticket_id)
        return folder_file(files, worker_session_id(ticket_id), path)

    @router.get("/{ticket_id}/images/{sha256}")
    async def read_ticket_image(ticket_id: str, sha256: str) -> FileResponse:
        tickets.get(ticket_id)
        return logged_image(images, await tickets.worker_events(ticket_id), sha256)

    return router
