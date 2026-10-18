"""Images by the rules: the types a model is sent, the 5 MB cap, bytes that match their hash."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from harness.files import ChatFile
from harness.images.models import ImageFile
from harness.images.repository import KEPT_MEDIA_TYPES, ImageRepository
from harness.llm import Block, Image, Text
from harness.prompts import IMAGE_TOO_LARGE
from harness.tools.definition import ReturnedImage

logger = logging.getLogger("harness.images")

IMAGE_MAX_BYTES = 5 * 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}")


def is_sha256(text: str) -> bool:
    """Whether `text` is a lowercase hex SHA-256."""
    return _SHA256.fullmatch(text) is not None


class ImageService:
    """The images a model is shown: kept from tool results and attachments, read back by hash."""

    def __init__(self, repository: ImageRepository) -> None:
        self._repository = repository

    def of_result(self, returned: tuple[ReturnedImage, ...]) -> tuple[Block, ...]:
        """Each image a tool returned, kept and shown; one too large is a note saying so instead."""
        blocks: list[Block] = []
        for image in returned:
            if image.media_type not in KEPT_MEDIA_TYPES:
                logger.warning(
                    "a tool's %s image is not shown: no model is sent that type", image.media_type
                )
                continue
            if len(image.data) > IMAGE_MAX_BYTES:
                note = IMAGE_TOO_LARGE.format(size=len(image.data), limit=IMAGE_MAX_BYTES)
                blocks.append(Text(text=note))
                continue
            kept = self._save(image.media_type, image.data)
            if kept is not None:
                blocks.append(kept)
        return tuple(blocks)

    def of_attachments(self, files: tuple[ChatFile, ...]) -> tuple[Image, ...]:
        """Each attachment a model can be sent as an image, kept; any other is left to its line."""
        images: list[Image] = []
        for file in files:
            if file.media_type not in KEPT_MEDIA_TYPES or file.size > IMAGE_MAX_BYTES:
                continue
            try:
                data = Path(file.path).read_bytes()
            except OSError as err:
                logger.warning("attached %s is not shown: %s", file.path, err)
                continue
            kept = self._save(file.media_type, data)
            if kept is not None:
                images.append(kept)
        return tuple(images)

    def read(self, image: Image) -> bytes | None:
        """The bytes `image` names; `None`, with a warning, when they cannot be read back."""
        if image.media_type not in KEPT_MEDIA_TYPES or not is_sha256(image.sha256):
            logger.warning("image %r (%s) cannot name a kept file", image.sha256, image.media_type)
            return None
        try:
            data = self._repository.read(image.sha256, image.media_type)
        except OSError as err:
            logger.warning("image %s could not be read: %s", image.sha256, err)
            return None
        if hashlib.sha256(data).hexdigest() != image.sha256:
            logger.warning("image %s no longer holds the bytes it is named for", image.sha256)
            return None
        return data

    def file_of(self, sha256: str) -> ImageFile | None:
        """The kept file named `sha256`, whatever its extension; `None` when there is none."""
        return self._repository.file_of(sha256) if is_sha256(sha256) else None

    def _save(self, media_type: str, data: bytes) -> Image | None:
        """The image `data` is, once kept; `None`, with a warning, when it could not be written."""
        image = Image(
            media_type=media_type, sha256=hashlib.sha256(data).hexdigest(), size=len(data)
        )
        try:
            self._repository.write(image.sha256, media_type, data)
        except OSError as err:
            logger.warning("an image is not shown: it could not be kept: %s", err)
            return None
        return image
