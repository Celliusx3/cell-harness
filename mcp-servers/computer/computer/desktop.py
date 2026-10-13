"""The computer's whole screen, read through the image's API endpoint."""

from __future__ import annotations

import base64
import binascii
import logging
import re
from collections.abc import Sequence
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from computer.docker import COMMAND_TIMEOUT_SECONDS, Docker, stdout_of
from computer.machine import API_PORT, API_TOKEN_VARIABLE, DISPLAY

logger = logging.getLogger("computer")

DESKTOP_TIMEOUT_SECONDS = 10.0
LOOPBACK = "127.0.0.1"
LOOPBACK_BINDING_PATTERN = re.compile(r"127\.0\.0\.1:(\d+)")
ENV_FORMAT = "{{json .Config.Env}}"
ENVIRONMENT: TypeAdapter[list[str]] = TypeAdapter(list[str])
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


def published_port(published: str, container_port: int) -> int:
    """The host port `docker port` names for a container port, refused unless it is loopback."""
    for line in published.splitlines():
        match = LOOPBACK_BINDING_PATTERN.fullmatch(line.strip())
        if match is not None:
            return int(match.group(1))
    raise DesktopError(
        f"The computer's port {container_port} is not published on {LOOPBACK}: "
        f"docker port said {published.strip()!r}."
    )


def api_token(inspected: str) -> str:
    """The API's bearer token, from `docker inspect` of the computer's environment."""
    try:
        env = ENVIRONMENT.validate_json(inspected)
    except ValidationError as err:
        raise DesktopError(
            "docker inspect answered the computer's environment with something this server "
            "cannot read."
        ) from err
    prefix = f"{API_TOKEN_VARIABLE}="
    token = next((entry.removeprefix(prefix) for entry in env if entry.startswith(prefix)), "")
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

    def __init__(self, *, docker: Docker, container: str, client: httpx.AsyncClient) -> None:
        self._docker = docker
        self._container = container
        self._client = client

    async def screenshot(self) -> Screenshot:
        asked = DesktopRequest(display=DISPLAY, steps=(), observe=True)
        what = "the screenshot"
        port = published_port(
            await self._output(["port", self._container, str(API_PORT)], "docker port"),
            API_PORT,
        )
        inspect = ["inspect", "--type", "container", "--format", ENV_FORMAT, self._container]
        token = api_token(await self._output(inspect, "docker inspect"))
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

    async def _output(self, args: Sequence[str], action: str) -> str:
        completed = await self._docker.run(args, stdin="", timeout_seconds=COMMAND_TIMEOUT_SECONDS)
        return stdout_of(completed, action)
