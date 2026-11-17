"""What a file or a chat's folder may be named, and the type a file's name implies."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from harness.files.domain.errors import UnsafeFileNameError

NOT_A_NAME = frozenset({"", ".", ".."})
UNKNOWN_MEDIA_TYPE = "application/octet-stream"


def is_plain_name(text: str) -> bool:
    """Whether `text` is one entry's name: not empty, `.`, `..`, a path, or holding a NUL."""
    return text not in NOT_A_NAME and Path(text).name == text and "\x00" not in text


def plain_name_of(name: str) -> str:
    """The last part of `name`; `UnsafeFileNameError` if it is empty, `.`, `..` or holds a NUL."""
    base = Path(name).name
    if not is_plain_name(base):
        raise UnsafeFileNameError(f"{name!r} does not name a file")
    return base


def media_type_of(name: str) -> str:
    """The type `name`'s extension implies, or `application/octet-stream`."""
    guessed, _ = mimetypes.guess_type(name)
    return guessed or UNKNOWN_MEDIA_TYPE
