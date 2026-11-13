"""A file from a chat's folder and an image from a chat's log, as a page reads them."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from harness.files import ChatFileService
from harness.images import ImageService
from harness.llm import images_of
from harness.session.models import SessionEvent, ToolResultEvent, UserMessageEvent

INLINE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
NO_SNIFFING = {"X-Content-Type-Options": "nosniff"}


def folder_file(files: ChatFileService, chat_id: str, path: str) -> FileResponse:
    """The file at `path` in `chat_id`'s folder: an image shown in place, anything else saved."""
    stored = files.file_at(chat_id, path)
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


def logged_image(images: ImageService, events: Sequence[SessionEvent], sha256: str) -> FileResponse:
    """The image kept under `sha256`, shown in place, when one of `events` showed it the model."""
    stored = images.file_of(sha256) if _shows(events, sha256) else None
    if stored is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"{sha256} is not an image in this chat",
            headers=NO_SNIFFING,
        )
    return FileResponse(
        stored.path,
        media_type=stored.media_type,
        filename=stored.path.name,
        content_disposition_type="inline",
        headers=NO_SNIFFING,
    )


def _shows(events: Sequence[SessionEvent], sha256: str) -> bool:
    return any(
        image.sha256 == sha256
        for event in events
        if isinstance(event, (UserMessageEvent, ToolResultEvent))
        for image in images_of(event.message)
    )
