"""What the four workspace tools are called with."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from harness.tools.native.workspace import _descriptions


class WorkspaceReadArgs(BaseModel):
    """What the model passes to `workspace_read`."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(description=_descriptions.PATH)
    start_line: int | None = Field(default=None, ge=1, description=_descriptions.START_LINE)
    end_line: int | None = Field(default=None, ge=1, description=_descriptions.END_LINE)


class WorkspaceWriteArgs(BaseModel):
    """What the model passes to `workspace_write`."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(description=_descriptions.PATH)
    text: str = Field(description=_descriptions.TEXT)


class WorkspaceEditArgs(BaseModel):
    """What the model passes to `workspace_edit`."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(description=_descriptions.PATH)
    find: str = Field(description=_descriptions.FIND)
    replace: str = Field(description=_descriptions.REPLACE)


class WorkspaceSearchArgs(BaseModel):
    """What the model passes to `workspace_search`."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(min_length=1, description=_descriptions.QUERY)
    path: str | None = Field(default=None, description=_descriptions.SEARCH_PATH)
