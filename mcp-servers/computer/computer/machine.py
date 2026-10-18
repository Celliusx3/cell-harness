"""The one computer: made, started, adopted at startup, and stopped when nobody uses it."""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Literal

from pydantic import TypeAdapter, ValidationError

from computer.clock import Clock
from computer.config import Config
from computer.docker import COMMAND_TIMEOUT_SECONDS, CommandResult, Docker, DockerError, stdout_of
from computer.jobs import RUNNING_JOBS_SCRIPT
from computer.mounts import MOUNTS_FORMAT, is_mounted_as_configured, volume_arguments

logger = logging.getLogger("computer")

HOME = "/home/rakazo"
JOBS_ROOT = f"{HOME}/.shell"
DISPLAY = ":1"
API_PORT = 7070
GATEWAY_PORT = 6080
API_TOKEN_VARIABLE = "RAKAZO_COMPUTER_CONTROL_TOKEN"
LABEL = "cell-harness.computer"
SHM_SIZE = "256m"
OPEN_CHROME_COMMAND = ["rakazo-focus-or-launch", "rakazo-browser"]
BINDINGS_FORMAT = "{{json .HostConfig.PortBindings}}"
PORT_BINDINGS: TypeAdapter[dict[str, list[dict[str, str]] | None] | None] = TypeAdapter(
    dict[str, list[dict[str, str]] | None] | None
)

ContainerState = Literal["running", "stopped", "missing"]


def run_arguments(config: Config, api_token: str) -> list[str]:
    """`docker run` as Rakazo creates its computer, with its API and gateway on loopback only."""
    name = config.container_name
    return [
        "run", "-d", "--name", name,
        "--label", f"{LABEL}={name}",
        "--shm-size", SHM_SIZE,
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        "-e", f"DISPLAY={DISPLAY}",
        "-e", f"HOME={HOME}",
        "-e", f"{API_TOKEN_VARIABLE}={api_token}",
        "-v", f"{name}-home:{HOME}",
        *volume_arguments(config),
        "-p", f"127.0.0.1::{API_PORT}",
        "-p", f"127.0.0.1::{GATEWAY_PORT}",
        config.image,
    ]  # fmt: skip


def state_of(inspected: CommandResult) -> ContainerState:
    if inspected.returncode != 0 and "No such container" in inspected.stderr:
        return "missing"
    status = stdout_of(inspected, "docker inspect").strip()
    return "running" if status == "running" else "stopped"


def publishes_gateway(inspected: str) -> bool:
    """Whether the container's port bindings, as `docker inspect` prints them, name the gateway."""
    try:
        bindings = PORT_BINDINGS.validate_json(inspected)
    except ValidationError as err:
        raise DockerError(
            "docker inspect answered the computer's ports with something this server cannot read"
        ) from err
    return f"{GATEWAY_PORT}/tcp" in (bindings or {})


class Machine:
    """One container per server process, shared by every bot."""

    def __init__(self, *, docker: Docker, config: Config, clock: Clock) -> None:
        self._docker = docker
        self._config = config
        self._clock = clock
        self._lock = asyncio.Lock()
        self._idle: asyncio.Task[None] | None = None
        self._idle_stop_paused = False
        self._shape_checked = False

    @asynccontextmanager
    async def serving(self) -> AsyncIterator[None]:
        """The server's lifespan: adopt a running computer, and leave it running on the way out."""
        await self._adopt()
        try:
            yield
        finally:
            self._cancel_idle_stop()

    @asynccontextmanager
    async def in_use(self) -> AsyncIterator[None]:
        """One tool call: the computer runs for its length, and the idle stop restarts after."""
        self._cancel_idle_stop()
        try:
            await self._ensure_running()
            yield
        finally:
            self._restart_idle_stop()

    def pause_idle_stop(self) -> None:
        """The person has the screen: the idle stop waits until they hand it back."""
        self._idle_stop_paused = True
        self._cancel_idle_stop()

    def resume_idle_stop(self) -> None:
        self._idle_stop_paused = False
        self._restart_idle_stop()

    async def _adopt(self) -> None:
        try:
            state = await self._state()
        except DockerError as err:
            logger.warning(
                "cannot see the computer %s at startup: %s", self._config.container_name, err
            )
            return
        if state == "running":
            logger.info("adopting the running computer %s", self._config.container_name)
            await self._open_chrome()
            self._restart_idle_stop()

    async def _ensure_running(self) -> None:
        async with self._lock:
            state = await self._state()
            if state != "missing" and not self._shape_checked:
                reason = await self._replacement_reason()
                if reason is not None:
                    logger.info(
                        "replacing the computer %s: %s", self._config.container_name, reason
                    )
                    await self._output(["rm", "-f", self._config.container_name], "docker rm")
                    state = "missing"
            self._shape_checked = True
            if state == "running":
                return
            if state == "stopped":
                await self._output(["start", self._config.container_name], "docker start")
            else:
                arguments = run_arguments(self._config, secrets.token_hex(16))
                await self._output(arguments, "docker run")
            await self._open_chrome()

    async def _open_chrome(self) -> None:
        try:
            await self._output(
                ["exec", "-d", self._config.container_name, *OPEN_CHROME_COMMAND], "opening Chrome"
            )
        except DockerError as err:
            logger.warning(
                "Chrome did not open on the computer %s: %s", self._config.container_name, err
            )

    async def _state(self) -> ContainerState:
        inspect = ["inspect", "--type", "container", "--format", "{{.State.Status}}"]
        return state_of(
            await self._docker.run(
                [*inspect, self._config.container_name],
                stdin="",
                timeout_seconds=COMMAND_TIMEOUT_SECONDS,
            )
        )

    async def _replacement_reason(self) -> str | None:
        """Why the existing container lacks the gateway port or the shared mounts, or None."""
        if not publishes_gateway(await self._inspect_output(BINDINGS_FORMAT)):
            return "it has no gateway port"
        if not is_mounted_as_configured(await self._inspect_output(MOUNTS_FORMAT), self._config):
            return "its mounts are not the shared folders"
        return None

    async def _inspect_output(self, template: str) -> str:
        inspect = ["inspect", "--type", "container", "--format", template]
        return await self._output([*inspect, self._config.container_name], "docker inspect")

    async def _output(self, args: Sequence[str], action: str) -> str:
        return stdout_of(
            await self._docker.run(args, stdin="", timeout_seconds=COMMAND_TIMEOUT_SECONDS),
            action,
        )

    def _restart_idle_stop(self) -> None:
        self._cancel_idle_stop()
        if not self._idle_stop_paused:
            self._idle = asyncio.create_task(self._stop_when_idle())

    def _cancel_idle_stop(self) -> None:
        if self._idle is not None:
            self._idle.cancel()
            self._idle = None

    async def _stop_when_idle(self) -> None:
        await self._clock.sleep(self._config.idle_minutes * 60)
        self._idle = None
        async with self._lock:
            name, minutes = self._config.container_name, self._config.idle_minutes
            if await self._is_running_a_command():
                logger.info("the computer %s stays on: a command is still running in it", name)
                self._restart_idle_stop()
                return
            logger.info("stopping the computer %s after %d idle minutes", name, minutes)
            try:
                await self._output(["stop", name], "docker stop")
            except DockerError as err:
                logger.warning("idle stop of the computer %s did not happen: %s", name, err)

    async def _is_running_a_command(self) -> bool:
        """Whether a bot's command still runs in the computer; True when that cannot be told."""
        name = self._config.container_name
        look = ["exec", name, "python3", "-c", RUNNING_JOBS_SCRIPT, JOBS_ROOT]
        try:
            return bool((await self._output(look, "looking for running commands")).split())
        except DockerError as err:
            logger.warning("the computer %s stays on: %s", name, err)
            return True
