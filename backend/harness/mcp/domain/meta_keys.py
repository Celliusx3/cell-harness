"""The `_meta` keys the harness puts in a `tools/call` request and reads from its result."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

WORKSPACE_META = "harness/workspace"
FILES_META = "io.cell-harness/files"


class ReturnedFile(BaseModel):
    """One entry of a tool result's `_meta` under FILES_META: a file the tool hands back."""

    model_config = ConfigDict(frozen=True)

    path: str
