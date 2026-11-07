"""The computer's whole screen, read by one command in the PC."""

from __future__ import annotations

import base64
import binascii
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from computer.engine import Engine
from computer.models.command import stdout_of
from computer.models.pc import Program
from computer.services.machine import DISPLAY

logger = logging.getLogger("computer")

DESKTOP_TIMEOUT_SECONDS = 10.0
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SCREENSHOT = Program(
    argv=("bash", "-o", "pipefail", "-c", "scrot - | base64 -w 0"), env={"DISPLAY": DISPLAY}
)


class DesktopError(RuntimeError):
    """The screen could not be read or reached. The message says why, for the person watching."""


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


class Desktop:
    """The computer's display, one command at a time."""

    def __init__(self, *, engine: Engine, container: str) -> None:
        self._engine = engine
        self._container = container

    async def screenshot(self) -> Screenshot:
        completed = await self._engine.run(
            self._container, SCREENSHOT, stdin=None, timeout_seconds=DESKTOP_TIMEOUT_SECONDS
        )
        image = stdout_of(completed, "the screenshot", error=DesktopError).strip()
        try:
            return Screenshot.model_validate({"image": image, "mimeType": "image/png"})
        except ValidationError as err:
            logger.error("the computer's screenshot was not a PNG: %s", err)
            raise DesktopError("The computer's screenshot is not a PNG.") from err
