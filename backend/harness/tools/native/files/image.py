"""A PNG or JPEG file of at most `IMAGE_MAX_BYTES`, read as a `ReturnedImage`."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from harness.images import IMAGE_MAX_BYTES
from harness.tools.definition import ReturnedImage

MEDIA_TYPE_BY_SIGNATURE: Mapping[bytes, str] = MappingProxyType(
    {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}
)


class UnviewableImage(ValueError):
    """A file that is not a PNG or JPEG, or is too large to show."""


def image_type(data: bytes) -> str | None:
    """`image/png` or `image/jpeg` when `data` opens with that format's signature; else `None`."""
    return next(
        (kind for mark, kind in MEDIA_TYPE_BY_SIGNATURE.items() if data.startswith(mark)), None
    )


def image_at(file: Path) -> ReturnedImage:
    """The PNG or JPEG at `file`, when it is at most `IMAGE_MAX_BYTES`."""
    with file.open("rb") as reader:
        data = reader.read(IMAGE_MAX_BYTES + 1)
    if len(data) > IMAGE_MAX_BYTES:
        raise UnviewableImage(
            f"{file} is larger than {IMAGE_MAX_BYTES} bytes, the most an image you view may be"
        )
    media_type = image_type(data)
    if media_type is None:
        raise UnviewableImage(f"{file} is not a PNG or JPEG image")
    return ReturnedImage(media_type=media_type, data=data)
