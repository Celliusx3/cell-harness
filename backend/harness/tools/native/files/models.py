"""What the four file tools are called with."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from harness.tools.native.files import descriptions


class SendFileArgs(BaseModel):
    """What the model passes to `send_file`."""

    model_config = ConfigDict(frozen=True)

    paths: list[str] = Field(min_length=1, description=descriptions.PATHS)


class ExtractArchiveArgs(BaseModel):
    """What the model passes to `extract_archive`."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(description=descriptions.ARCHIVE_PATH)


class MakeArchiveArgs(BaseModel):
    """What the model passes to `make_archive`."""

    model_config = ConfigDict(frozen=True)

    paths: list[str] = Field(min_length=1, description=descriptions.ARCHIVE_PATHS)
    name: str = Field(description=descriptions.ARCHIVE_NAME)


class ViewImageArgs(BaseModel):
    """What the model passes to `view_image`."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(description=descriptions.IMAGE_PATH)
