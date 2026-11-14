"""Where the images a model is shown are kept: their bytes, under the hash of those bytes."""

from __future__ import annotations

from typing import Protocol, TypeIs, get_args

from harness.images.domain.models import ImageFile, KeptMediaType

KEPT_MEDIA_TYPES: frozenset[str] = frozenset(get_args(KeptMediaType))


def is_kept_media_type(media_type: str) -> TypeIs[KeptMediaType]:
    """Whether an image of `media_type` is one a model can be sent, so one we keep."""
    return media_type in KEPT_MEDIA_TYPES


class ImageRepository(Protocol):
    """Image bytes kept by their hash, as storage."""

    def write(self, sha256: str, media_type: KeptMediaType, data: bytes) -> None:
        """`data` kept under `sha256` once; a second write of the same hash changes nothing."""
        ...

    def read(self, sha256: str, media_type: KeptMediaType) -> bytes:
        """The bytes kept under `sha256`; `OSError` when there are none."""
        ...

    def file_of(self, sha256: str) -> ImageFile | None:
        """The kept file named `sha256`, whatever its extension; `None` when there is none."""
        ...
