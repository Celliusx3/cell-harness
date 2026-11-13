"""A file a chat holds, as the log records it."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ChatFile(BaseModel):
    """A file in a chat's folder: where it is on disk, its name, type and size."""

    model_config = ConfigDict(frozen=True)

    path: str
    name: str
    media_type: str
    size: int
