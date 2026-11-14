"""A kept image's file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

KeptMediaType = Literal["image/png", "image/jpeg", "image/webp", "image/gif"]


@dataclass(frozen=True)
class ImageFile:
    """An image's file, and the media type its extension names."""

    path: Path
    media_type: KeptMediaType
