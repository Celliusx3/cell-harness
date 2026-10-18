"""Programs on the Mac that skills declare: run for this server's life, reached by commands."""

from __future__ import annotations

import asyncio
import logging
import secrets
import shutil
import socket
import tempfile
from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from computer.clock import Clock

logger = logging.getLogger("computer")

LOOPBACK = "127.0.0.1"
HOST_FROM_THE_COMPUTER = "host.docker.internal"
TOKEN_BYTES = 32
TOKEN_FOLDER_PREFIX = "cell-harness-host-service-"
TOKEN_FILE_NAME = "token"
STARTUP_SECONDS = 20.0
POLL_SECONDS = 0.1


class HostServiceError(RuntimeError):
    """A declared program did not start. The message says why."""


@dataclass(frozen=True)
class HostService:
    """A declared program found on the Mac: whose it is, its path, words and variables' prefix."""

    skill: str
    env_prefix: str
    program: Path
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class PreparedHostService:
    """A declared program with what fills its placeholders but the token file; not started yet."""

    service: HostService
    port: int
    token: str
    files: Path


def free_loopback_port() -> int:
    """A port on 127.0.0.1 that nothing is bound to, as the system hands one out."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((LOOPBACK, 0))
        return int(probe.getsockname()[1])


def prepared_host_service(service: HostService, files: Path) -> PreparedHostService:
    """`service` on a free loopback port with a new 64-hex token, `files` as its {files}."""
    return PreparedHostService(
        service=service,
        port=free_loopback_port(),
        token=secrets.token_hex(TOKEN_BYTES),
        files=files,
    )


def command_variables(prepared: Sequence[PreparedHostService]) -> dict[str, str]:
    """What a command in the computer reads to reach each service: `<PREFIX>_ADDR`, `_TOKEN`."""
    return {
        name: value
        for each in prepared
        for name, value in (
            (f"{each.service.env_prefix}_ADDR", f"{HOST_FROM_THE_COMPUTER}:{each.port}"),
            (f"{each.service.env_prefix}_TOKEN", each.token),
        )
    }


def launch_arguments(prepared: PreparedHostService, token_file: Path) -> list[str]:
    """The program and its argument words with {port}, {token_file} and {files} filled in."""
    values = {
        "port": str(prepared.port),
        "token_file": str(token_file),
        "files": str(prepared.files),
    }
    return [
        str(prepared.service.program),
        *(word.format(**values) for word in prepared.service.arguments),
    ]


@asynccontextmanager
async def serving_host_service(prepared: PreparedHostService, clock: Clock) -> AsyncIterator[None]:
    """The program listening for the body; killed, waited on and its token removed after it."""
    folder = Path(tempfile.mkdtemp(prefix=TOKEN_FOLDER_PREFIX))
    try:
        token_file = folder / TOKEN_FILE_NAME
        token_file.touch(mode=0o600, exist_ok=False)
        token_file.write_text(prepared.token, encoding="ascii")
        process = await start_program(launch_arguments(prepared, token_file))
        try:
            await wait_until_listening(process, prepared, clock)
            logger.info(
                "the skill %s's %s serves the computer on %s:%d as %s_ADDR",
                prepared.service.skill,
                prepared.service.program.name,
                LOOPBACK,
                prepared.port,
                prepared.service.env_prefix,
            )
            yield
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()
    finally:
        shutil.rmtree(folder)


@asynccontextmanager
async def serving_host_services_that_start(
    prepared: Sequence[PreparedHostService], clock: Clock
) -> AsyncIterator[None]:
    """Each service that starts listening for the body; one that does not is logged, not raised."""
    async with AsyncExitStack() as stack:
        for each in prepared:
            try:
                await stack.enter_async_context(serving_host_service(each, clock))
            except HostServiceError as err:
                logger.warning(
                    "the skill %s's program did not start, so commands in the computer run "
                    "without it: %s",
                    each.service.skill,
                    err,
                )
        yield


async def start_program(arguments: Sequence[str]) -> asyncio.subprocess.Process:
    """The program running, its stdin and stdout kept off this server's MCP stream."""
    try:
        return await asyncio.create_subprocess_exec(
            *arguments, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL
        )
    except OSError as err:
        raise HostServiceError(f"{arguments[0]} could not be started: {err}") from err


async def wait_until_listening(
    process: asyncio.subprocess.Process, prepared: PreparedHostService, clock: Clock
) -> None:
    """Back once the port takes a connection; a refusal when the program exits or never listens."""
    door, program = f"{LOOPBACK}:{prepared.port}", prepared.service.program
    began = clock.now()
    while clock.now() - began < STARTUP_SECONDS:
        if process.returncode is not None:
            raise HostServiceError(
                f"{program} exited with code {process.returncode} before it listened on {door}"
            )
        if await is_listening(prepared.port):
            return
        await clock.sleep(POLL_SECONDS)
    raise HostServiceError(f"{program} did not listen on {door} within {STARTUP_SECONDS:g} seconds")


async def is_listening(port: int) -> bool:
    try:
        _, writer = await asyncio.open_connection(LOOPBACK, port)
    except OSError:
        return False
    writer.close()
    await writer.wait_closed()
    return True
