"""The phone's screen, read by one command inside Android."""

from __future__ import annotations

import base64
import binascii
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from phone.engine import Engine
from phone.models.command import stdout_of
from phone.models.phone import Program

logger = logging.getLogger("phone")

SCREEN_TIMEOUT_SECONDS = 10.0
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SCREENSHOT = Program(argv=("android", "screencap -p | base64 -w 0"), env={})


class ScreenError(RuntimeError):
    """The screen could not be read. The message says why, in plain words."""


class Screenshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    image: str
    mime_type: Literal["image/png"] = Field(alias="mimeType")

    @field_validator("image")
    @classmethod
    def checked_png(cls, image: str) -> str:
        try:
            decoded = base64.b64decode(image, validate=True)
        except binascii.Error as err:
            raise ValueError("image is not base64") from err
        if not decoded.startswith(PNG_SIGNATURE):
            raise ValueError("image is not a PNG")
        return image


class Screen:
    """The phone's display, one command at a time."""

    def __init__(self, *, engine: Engine, name: str) -> None:
        self._engine = engine
        self._name = name

    async def screenshot(self) -> Screenshot:
        completed = await self._engine.run(
            self._name, SCREENSHOT, stdin=None, timeout_seconds=SCREEN_TIMEOUT_SECONDS
        )
        image = stdout_of(completed, "The phone's screenshot", error=ScreenError).strip()
        try:
            return Screenshot.model_validate({"image": image, "mimeType": "image/png"})
        except ValidationError as err:
            logger.error("the phone's screenshot was not a PNG: %s", err)
            raise ScreenError("The phone's screenshot is not a PNG.") from err
