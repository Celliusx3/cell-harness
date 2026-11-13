"""A file a tool hands back, named in its result's `_meta`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

FILES_META = "io.cell-harness/files"


class ReturnedFile(BaseModel):
    """One entry of a tool result's `_meta` under FILES_META: a file the tool hands back."""

    model_config = ConfigDict(frozen=True)

    path: str
