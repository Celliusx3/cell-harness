"""The computer's whole screen, read through the image's API endpoint."""

from __future__ import annotations

import base64
import binascii
import logging
from collections.abc import Mapping
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from computer.engine import LOOPBACK, Engine
from computer.services.machine import API_PORT, API_TOKEN_VARIABLE, DISPLAY

logger = logging.getLogger("computer")

DESKTOP_TIMEOUT_SECONDS = 10.0
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


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


class DesktopReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    observation: Screenshot


def api_token(env: Mapping[str, str]) -> str:
    """The API's bearer token, from the variables the computer was made with."""
    token = env.get(API_TOKEN_VARIABLE, "")
    if not token:
        raise DesktopError(f"The computer has no API token: {API_TOKEN_VARIABLE} is not set.")
    return token


class DesktopRequest(BaseModel):
    """The API endpoint's body: run no steps, then look at the screen."""

    model_config = ConfigDict(frozen=True)

    display: str
    steps: tuple[()]
    observe: Literal[True]


class Desktop:
    """The computer's display, one request at a time; port and token are read on every call."""

    def __init__(self, *, engine: Engine, container: str, client: httpx.AsyncClient) -> None:
        self._engine = engine
        self._container = container
        self._client = client

    async def screenshot(self) -> Screenshot:
        asked = DesktopRequest(display=DISPLAY, steps=(), observe=True)
        what = "the screenshot"
        port = await self._engine.host_port(self._container, API_PORT)
        token = api_token(await self._engine.environment(self._container))
        try:
            response = await self._client.post(
                f"http://{LOOPBACK}:{port}/v1/desktop",
                headers={"Authorization": f"Bearer {token}"},
                json=asked.model_dump(mode="json"),
                timeout=DESKTOP_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as err:
            raise DesktopError(
                f"The computer's screen did not answer: {type(err).__name__}: {err}"
            ) from err
        if response.status_code != httpx.codes.OK:
            logger.error("the computer's API endpoint refused %s: %s", what, response.text)
            raise DesktopError(
                f"The computer refused {what}: {response.status_code} {response.reason_phrase}."
            )
        try:
            return DesktopReply.model_validate_json(response.content).observation
        except ValidationError as err:
            logger.error("the computer's API endpoint answered %s with: %s", what, err)
            raise DesktopError(
                f"The computer answered {what} with something this server cannot read."
            ) from err
