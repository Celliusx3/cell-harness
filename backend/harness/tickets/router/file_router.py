"""The files in a ticket's worker folder and the images its worker's log shows, for its page."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from harness.files import ChatFileService
from harness.images import ImageService
from harness.tickets.service.ticket_service import TicketService
from harness.tickets.service.worker import worker_session_id
from harness.web.http.files import folder_file, logged_image


class TicketFileRouter:
    """Read a file from a ticket's worker folder, and an image its worker's log shows."""

    def __init__(
        self, tickets: TicketService, files: ChatFileService, images: ImageService
    ) -> None:
        self._tickets = tickets
        self._files = files
        self._images = images
        self.router: APIRouter = APIRouter(prefix="/api/tickets", tags=["tickets"])
        self.router.add_api_route("/{ticket_id}/file", self.read_ticket_file, methods=["GET"])
        self.router.add_api_route(
            "/{ticket_id}/images/{sha256}", self.read_ticket_image, methods=["GET"]
        )

    async def read_ticket_file(self, ticket_id: str, path: str) -> FileResponse:
        self._tickets.get(ticket_id)
        return folder_file(self._files, worker_session_id(ticket_id), path)

    async def read_ticket_image(self, ticket_id: str, sha256: str) -> FileResponse:
        self._tickets.get(ticket_id)
        return logged_image(self._images, await self._tickets.worker_events(ticket_id), sha256)
