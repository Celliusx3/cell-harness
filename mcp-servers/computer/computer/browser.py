"""Rakazo's page script inside the computer: one JSON line in on stdin, one JSON object out."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from computer.clock import Clock
from computer.docker import COMMAND_TIMEOUT_SECONDS, Docker, DockerTimeout, stdout_of
from computer.machine import OPEN_CHROME_COMMAND
from computer.models import Acted, Action, Opened, Page

logger = logging.getLogger("computer")

PAGE_TIMEOUT_SECONDS = 25.0
CHROME_WAIT_SECONDS = 15.0
RETRY_SECONDS = 0.5
CHROME_DOWN = "CDP not ready"
PAGE_SCRIPT = ["rakazo-page-browser"]
ARGUMENTS_ON_STDIN = "RAKAZO_BROWSER_ARGS_STDIN=1"
NO_ARGUMENTS = "{}"

PageCommand = Literal["navigate", "snapshot", "act"]


class BrowserError(RuntimeError):
    """The page script failed, or answered with something this server cannot read."""


class Reply(BaseModel):
    model_config = ConfigDict(frozen=True)


class Refusal(Reply):
    ok: Literal[False]
    error: str
    completed: int = 0
    uncertain: bool = False


class Navigated(Reply):
    ok: Literal[True]
    url: str
    title: str


class Snapshot(Reply):
    ok: Literal[True]
    url: str
    title: str
    tree: str


class ActReply(Snapshot):
    completed: int


NAVIGATE_REPLY: TypeAdapter[Navigated | Refusal] = TypeAdapter(
    Annotated[Navigated | Refusal, Field(discriminator="ok")]
)
SNAPSHOT_REPLY: TypeAdapter[Snapshot | Refusal] = TypeAdapter(
    Annotated[Snapshot | Refusal, Field(discriminator="ok")]
)
ACT_REPLY: TypeAdapter[ActReply | Refusal] = TypeAdapter(
    Annotated[ActReply | Refusal, Field(discriminator="ok")]
)


class NavigateArguments(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str


class ActArguments(BaseModel):
    model_config = ConfigDict(frozen=True)

    actions: list[Action]


def sentence(text: str) -> str:
    stripped = text.strip()
    return stripped if stripped.endswith((".", "!", "?")) else f"{stripped}."


def is_chrome_down(reply: Reply) -> bool:
    return isinstance(reply, Refusal) and CHROME_DOWN in reply.error


def act_failure_message(refusal: Refusal, total: int) -> str:
    landed = " and may have taken effect" if refusal.uncertain else ""
    return (
        f"{refusal.completed} of {total} actions completed, then one failed{landed}: "
        f"{sentence(refusal.error)} Call browser_read_page before going on."
    )


class Browser:
    """The computer's Chrome, driven one page command at a time."""

    def __init__(self, *, docker: Docker, container: str, clock: Clock) -> None:
        self._docker = docker
        self._container = container
        self._clock = clock

    async def navigate(self, url: str) -> Opened:
        arguments = NavigateArguments(url=url).model_dump_json()
        reply = await self._ask("navigate", arguments, NAVIGATE_REPLY)
        if isinstance(reply, Refusal):
            raise BrowserError(f"Opening {url} failed: {sentence(reply.error)}")
        return Opened(url=reply.url, title=reply.title)

    async def read(self) -> Page:
        reply = await self._ask("snapshot", NO_ARGUMENTS, SNAPSHOT_REPLY)
        if isinstance(reply, Refusal):
            raise BrowserError(f"Reading the page failed: {sentence(reply.error)}")
        return Page(url=reply.url, title=reply.title, content=reply.tree)

    async def act(self, actions: Sequence[Action]) -> Acted:
        arguments = ActArguments(actions=list(actions)).model_dump_json(exclude_none=True)
        reply = await self._ask("act", arguments, ACT_REPLY)
        if isinstance(reply, Refusal):
            raise BrowserError(act_failure_message(reply, len(actions)))
        return Acted(
            url=reply.url,
            title=reply.title,
            content=reply.tree,
            actions_completed=reply.completed,
        )

    async def _ask[R: Reply](
        self, command: PageCommand, arguments: str, reply_type: TypeAdapter[R]
    ) -> R:
        started = self._clock.now()
        answer = await self._ask_once(command, arguments, reply_type)
        if not is_chrome_down(answer):
            return answer
        await self._open_chrome()
        while self._clock.now() - started < CHROME_WAIT_SECONDS:
            await self._clock.sleep(RETRY_SECONDS)
            answer = await self._ask_once(command, arguments, reply_type)
            if not is_chrome_down(answer):
                return answer
        raise BrowserError(
            f"Chrome on the computer did not start within {CHROME_WAIT_SECONDS:g} seconds. "
            "Try again in a minute; if it fails again, tell the person."
        )

    async def _ask_once[R: Reply](
        self, command: PageCommand, arguments: str, reply_type: TypeAdapter[R]
    ) -> R:
        script = ["exec", "-i", "-e", ARGUMENTS_ON_STDIN, self._container, *PAGE_SCRIPT, command]
        try:
            completed = await self._docker.run(
                script, stdin=arguments + "\n", timeout_seconds=PAGE_TIMEOUT_SECONDS
            )
        except DockerTimeout as err:
            raise BrowserError(
                f"The page did not answer within {PAGE_TIMEOUT_SECONDS:g} seconds. "
                "Call browser_read_page to see where it got to."
            ) from err
        raw = stdout_of(completed, f"rakazo-page-browser {command}")
        try:
            return reply_type.validate_json(raw)
        except ValidationError as err:
            logger.error("rakazo-page-browser %s answered %r: %s", command, raw, err)
            raise BrowserError(
                f"The computer answered {command} with something this server cannot read. "
                "This is a fault in the computer, not in the call: tell the person."
            ) from err

    async def _open_chrome(self) -> None:
        logger.info("Chrome is not up on the computer %s; launching it", self._container)
        launch = ["exec", "-d", self._container, *OPEN_CHROME_COMMAND]
        stdout_of(
            await self._docker.run(launch, stdin="", timeout_seconds=COMMAND_TIMEOUT_SECONDS),
            "launching Chrome",
        )
