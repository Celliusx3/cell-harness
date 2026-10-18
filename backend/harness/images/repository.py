"""Where the images a model is shown are kept: their bytes, under the hash of those bytes."""

from __future__ import annotations

from typing import Protocol

from harness.images.models import ImageFile

KEPT_MEDIA_TYPES: frozenset[str] = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})


class ImageRepository(Protocol):
    """Image bytes kept by their hash, as storage."""

    def write(self, sha256: str, media_type: str, data: bytes) -> None:
        """`data` kept under `sha256` once; a second write of the same hash changes nothing."""
        ...

    def read(self, sha256: str, media_type: str) -> bytes:
        """The bytes kept under `sha256`; `OSError` when there are none."""
        ...

    def file_of(self, sha256: str) -> ImageFile | None:
        """The kept file named `sha256`, whatever its extension; `None` when there is none."""
        ...
