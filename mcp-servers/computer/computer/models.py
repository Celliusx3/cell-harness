"""What the tools take and return; home_path is adapted from Rakazo (see NOTICE)."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from computer.machine import HOME

ActionKind = Literal["click", "fill", "type"]
ScreenMode = Literal["view", "control"]
FileKind = Literal["file", "dir"]
CommandStatus = Literal["done", "running"]

TRANSFER_LIMIT_BYTES = 10 * 1024 * 1024


class Action(BaseModel):
    """One step on the open page; fill replaces a field's value, type adds to it."""

    model_config = ConfigDict(frozen=True)

    kind: ActionKind
    ref: str = Field(min_length=1, description="From the newest page content.")
    text: str | None = Field(default=None, description="Required for fill and type; not click.")

    @model_validator(mode="after")
    def text_fits_kind(self) -> Self:
        if self.kind == "click" and self.text is not None:
            raise ValueError("click takes no text")
        if self.kind != "click" and self.text is None:
            raise ValueError(f"{self.kind} needs text")
        return self


class Opened(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    title: str


class Page(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    title: str
    content: str


class Acted(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    title: str
    content: str
    actions_completed: int


class ScreenSession(BaseModel):
    """The person's screen: watched, or controlled until held_until (UTC)."""

    model_config = ConfigDict(frozen=True)

    mode: ScreenMode
    held_until: datetime | None


@dataclass(frozen=True)
class HomePath:
    """A path in the home folder, as `home_path` read it."""

    relative: str

    @property
    def absolute(self) -> str:
        return f"{HOME}/{self.relative}" if self.relative else HOME


def home_path(path: str) -> HomePath:
    """Rakazo's reading: backslashes are slashes, empty segments go, and . or .. is refused."""
    if "\x00" in path:
        raise ValueError("a path cannot hold a NUL character")
    segments = [segment for segment in path.replace("\\", "/").split("/") if segment]
    if any(segment in (".", "..") for segment in segments):
        raise ValueError("a path stays in the home folder: no . or .. segments")
    return HomePath(relative="/".join(segments))


def checked_file_path(path: HomePath) -> HomePath:
    if not path.relative:
        raise ValueError("a path names a file in the home folder, not the folder itself")
    return path


def checked_upload(content_base64: str) -> str:
    try:
        size = len(base64.b64decode(content_base64, validate=True))
    except binascii.Error as err:
        raise ValueError("content_base64 is not base64") from err
    if size > TRANSFER_LIMIT_BYTES:
        raise ValueError("a file is at most 10 MiB")
    return content_base64


if TYPE_CHECKING:
    FolderPath = HomePath
    FilePath = HomePath
else:
    # The MCP SDK json.loads an argument not annotated `str`, which would turn "null" into None.
    FolderPath = Annotated[
        str,
        AfterValidator(home_path),
        Field(description="Relative to the home folder; empty for the home folder itself."),
    ]
    FilePath = Annotated[
        str,
        AfterValidator(home_path),
        AfterValidator(checked_file_path),
        Field(description="Relative to the home folder."),
    ]
UploadContent = Annotated[
    str,
    AfterValidator(checked_upload),
    Field(description="The file's bytes, base64; at most 10 MiB."),
]


class FileEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    kind: FileKind
    size: int


class Listing(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    entries: list[FileEntry]


class FileText(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    content: str


class FileBytes(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    content_base64: str


class Uploaded(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    size: int


class CommandRun(BaseModel):
    """A bot's command: still running with its output so far, or done with its exit code."""

    model_config = ConfigDict(frozen=True)

    status: CommandStatus
    exit_code: int | None
    seconds: float
    output: str

    @model_validator(mode="after")
    def exit_code_fits_status(self) -> Self:
        if (self.status == "running") != (self.exit_code is None):
            raise ValueError("a running command has no exit code yet, and a done one has one")
        return self
