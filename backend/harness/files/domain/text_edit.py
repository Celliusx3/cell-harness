"""A workspace file's text as the tools change it: its version, and the rule an edit follows."""

from __future__ import annotations

from hashlib import sha256

from pydantic import BaseModel, ConfigDict

from harness.files.domain.errors import (
    ChangedSinceReadError,
    EmptyFindError,
    FindMismatchError,
    NotReadError,
)

MAX_TEXT_BYTES = 2 * 1024 * 1024


class TextEdit(BaseModel):
    """One exact piece of a file's text, and the text that takes its place."""

    model_config = ConfigDict(frozen=True)

    find: str
    replace: str


def version_of(text: str) -> str:
    """The hex sha256 of `text`'s UTF-8 bytes, which are the bytes of the file it was read from."""
    return sha256(text.encode("utf-8")).hexdigest()


def unchanged_since_read(text: str, read_version: str | None, path: str) -> str:
    """`text`, when it is what was last read of `path`; refused when unread or changed since."""
    if read_version is None:
        raise NotReadError(path)
    if version_of(text) != read_version:
        raise ChangedSinceReadError(path)
    return text


def occurrences(text: str, find: str) -> int:
    """How many places `find` starts at in `text`, overlapping ones included."""
    count, start = 0, text.find(find)
    while start != -1:
        count += 1
        start = text.find(find, start + 1)
    return count


def crlf(text: str) -> str:
    """`text` with every line break written as `\\r\\n`."""
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def edited(text: str, find: str, replace: str) -> str:
    """`text` with its one `find` replaced; refused when `find` is empty or not there once."""
    if not find:
        raise EmptyFindError()
    if find not in text and "\r\n" in text:
        find, replace = crlf(find), crlf(replace)
    count = occurrences(text, find)
    if count != 1:
        raise FindMismatchError(count)
    return text.replace(find, replace, 1)
