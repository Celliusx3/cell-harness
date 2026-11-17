"""A kept image's file, the types we keep, and the hash an image is named by."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeIs, get_args

KeptMediaType = Literal["image/png", "image/jpeg", "image/webp", "image/gif"]
KEPT_MEDIA_TYPES: frozenset[str] = frozenset(get_args(KeptMediaType))
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class ImageFile:
    """An image's file, and the media type its extension names."""

    path: Path
    media_type: KeptMediaType


def is_kept_media_type(media_type: str) -> TypeIs[KeptMediaType]:
    """Whether an image of `media_type` is one a model can be sent, so one we keep."""
    return media_type in KEPT_MEDIA_TYPES


def is_sha256(text: str) -> bool:
    """Whether `text` is a lowercase hex SHA-256."""
    return _SHA256.fullmatch(text) is not None
