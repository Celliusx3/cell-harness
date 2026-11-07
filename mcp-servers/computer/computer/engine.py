"""What runs the PC, in the PC's own terms, and the docker engine that does it today."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from computer.docker import Docker
from computer.models.command import COMMAND_TIMEOUT_SECONDS, CommandResult, stdout_of
from computer.models.errors import EngineError
from computer.models.pc import PcSpec, PcState, Program, SharedFolder

LOOPBACK = "127.0.0.1"
LOOPBACK_BINDING_PATTERN = re.compile(r"127\.0\.0\.1:(\d+)")
LABEL = "cell-harness.computer"
HOST_FROM_THE_PC = "host.docker.internal"
STATUS_FORMAT = "{{.State.Status}}"
BINDINGS_FORMAT = "{{json .HostConfig.PortBindings}}"
MOUNTS_FORMAT = "{{json .Mounts}}"
ENV_FORMAT = "{{json .Config.Env}}"
PORT_BINDINGS: TypeAdapter[dict[str, list[dict[str, str]] | None] | None] = TypeAdapter(
    dict[str, list[dict[str, str]] | None] | None
)
ENVIRONMENT: TypeAdapter[list[str]] = TypeAdapter(list[str])


class Engine(Protocol):
    """The PC's lifecycle and the programs run in it; failing to reach it is an EngineError."""

    @property
    def host_address(self) -> str:
        """The Mac's address as a program in the PC reaches it."""

    async def create(self, spec: PcSpec) -> None:
        """Make the PC and start it."""

    async def start(self, name: str) -> None: ...

    async def stop(self, name: str) -> None: ...

    async def remove(self, name: str) -> None:
        """Remove the PC, running or not; its home volume stays."""

    async def state(self, name: str) -> PcState: ...

    async def replacement_reason(self, spec: PcSpec) -> str | None:
        """Why the PC lacks the spec's published ports or shared folders, or None."""

    async def host_port(self, name: str, guest_port: int) -> int:
        """The loopback port on the Mac that `guest_port` is published on."""

    async def environment(self, name: str) -> dict[str, str]:
        """The variables the PC was made with."""

    async def run(
        self, name: str, program: Program, *, stdin: str | None, timeout_seconds: float
    ) -> CommandResult:
        """Run `program` to its end; None attaches no stdin. A non-zero exit is returned."""

    async def launch(self, name: str, program: Program) -> CommandResult:
        """Start `program` detached; the result is the launch's, not the program's."""


class Mount(BaseModel):
    """One of the container's mounts, in the field names `docker inspect` prints."""

    model_config = ConfigDict(frozen=True)

    type: str = Field(alias="Type")
    source: str = Field(alias="Source")
    destination: str = Field(alias="Destination")
    read_write: bool = Field(alias="RW")


MOUNTS: TypeAdapter[list[Mount]] = TypeAdapter(list[Mount])


def bind_mount(folder: SharedFolder) -> Mount:
    return Mount(
        Type="bind", Source=str(folder.path), Destination=str(folder.path), RW=folder.writable
    )


def volume_arguments(spec: PcSpec) -> list[str]:
    """`-v` for the home volume and each shared folder, a read-only one ending in `:ro`."""
    shared = (
        f"{folder.path}:{folder.path}{'' if folder.writable else ':ro'}"
        for folder in spec.shared_folders
    )
    volumes = [f"{spec.home.name}:{spec.home.guest_path}", *shared]
    return [arg for volume in volumes for arg in ("-v", volume)]


def run_arguments(spec: PcSpec) -> list[str]:
    """`docker run` as Rakazo creates its computer."""
    return [
        "run", "-d", "--name", spec.name,
        "--label", f"{LABEL}={spec.name}",
        "--shm-size", f"{spec.shm_megabytes}m",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        *(arg for name, value in spec.env.items() for arg in ("-e", f"{name}={value}")),
        *volume_arguments(spec),
        *(arg for port in spec.published_ports for arg in ("-p", f"{LOOPBACK}::{port}")),
        spec.image,
    ]  # fmt: skip


def exec_arguments(name: str, program: Program, mode: Literal["-i", "-d"] | None) -> list[str]:
    """`docker exec` with its mode, the program's variables, the container and the program."""
    variables = [arg for key, value in program.env.items() for arg in ("-e", f"{key}={value}")]
    return ["exec", *([mode] if mode else []), *variables, name, *program.argv]


def inspect_arguments(name: str, template: str) -> list[str]:
    return ["inspect", "--type", "container", "--format", template, name]


def state_of(inspected: CommandResult) -> PcState:
    if inspected.returncode != 0 and "No such container" in inspected.stderr:
        return "missing"
    status = stdout_of(inspected, "docker inspect").strip()
    return "running" if status == "running" else "stopped"


def unpublished_ports(inspected: str, ports: tuple[int, ...]) -> list[int]:
    """Which of `ports` the container's bindings, as `docker inspect` prints them, leave out."""
    try:
        bindings = PORT_BINDINGS.validate_json(inspected)
    except ValidationError as err:
        raise EngineError(
            "docker inspect answered the computer's ports with something this server cannot read"
        ) from err
    return [port for port in ports if f"{port}/tcp" not in (bindings or {})]


def is_mounted_as(inspected: str, folders: tuple[SharedFolder, ...]) -> bool:
    """Whether the container's bind mounts, as `docker inspect` prints them, are `folders`."""
    try:
        mounts = MOUNTS.validate_json(inspected)
    except ValidationError as err:
        raise EngineError(
            "docker inspect answered the computer's mounts with something this server cannot read"
        ) from err
    binds = frozenset(mount for mount in mounts if mount.type == "bind")
    return binds == frozenset(bind_mount(folder) for folder in folders)


def loopback_port(published: str, guest_port: int) -> int:
    """The host port `docker port` names for a guest port, refused unless it is loopback."""
    for line in published.splitlines():
        match = LOOPBACK_BINDING_PATTERN.fullmatch(line.strip())
        if match is not None:
            return int(match.group(1))
    raise EngineError(
        f"The computer's port {guest_port} is not published on {LOOPBACK}: "
        f"docker port said {published.strip()!r}."
    )


def environment_of(inspected: str) -> dict[str, str]:
    """The variables `docker inspect` prints as the container's environment."""
    try:
        entries = ENVIRONMENT.validate_json(inspected)
    except ValidationError as err:
        raise EngineError(
            "docker inspect answered the computer's environment with something this server "
            "cannot read."
        ) from err
    if any("=" not in entry for entry in entries):
        raise EngineError("docker inspect answered the computer's environment without values.")
    return dict(entry.split("=", 1) for entry in entries)


@dataclass(frozen=True)
class DockerEngine:
    """The PC as one docker container, run through the docker command line."""

    docker: Docker

    @property
    def host_address(self) -> str:
        return HOST_FROM_THE_PC

    async def create(self, spec: PcSpec) -> None:
        await self._output(run_arguments(spec), "docker run")

    async def start(self, name: str) -> None:
        await self._output(["start", name], "docker start")

    async def stop(self, name: str) -> None:
        await self._output(["stop", name], "docker stop")

    async def remove(self, name: str) -> None:
        await self._output(["rm", "-f", name], "docker rm")

    async def state(self, name: str) -> PcState:
        return state_of(await self._cli(inspect_arguments(name, STATUS_FORMAT)))

    async def replacement_reason(self, spec: PcSpec) -> str | None:
        bindings = await self._inspected(spec.name, BINDINGS_FORMAT)
        unpublished = unpublished_ports(bindings, spec.published_ports)
        if unpublished:
            return f"it does not publish the port {unpublished[0]}"
        if not is_mounted_as(await self._inspected(spec.name, MOUNTS_FORMAT), spec.shared_folders):
            return "its mounts are not the shared folders"
        return None

    async def host_port(self, name: str, guest_port: int) -> int:
        published = await self._output(["port", name, str(guest_port)], "docker port")
        return loopback_port(published, guest_port)

    async def environment(self, name: str) -> dict[str, str]:
        return environment_of(await self._inspected(name, ENV_FORMAT))

    async def run(
        self, name: str, program: Program, *, stdin: str | None, timeout_seconds: float
    ) -> CommandResult:
        mode: Literal["-i"] | None = None if stdin is None else "-i"
        return await self.docker.run(
            exec_arguments(name, program, mode), stdin=stdin or "", timeout_seconds=timeout_seconds
        )

    async def launch(self, name: str, program: Program) -> CommandResult:
        return await self._cli(exec_arguments(name, program, "-d"))

    async def _inspected(self, name: str, template: str) -> str:
        return await self._output(inspect_arguments(name, template), "docker inspect")

    async def _output(self, args: list[str], action: str) -> str:
        return stdout_of(await self._cli(args), action)

    async def _cli(self, args: list[str]) -> CommandResult:
        return await self.docker.run(args, stdin="", timeout_seconds=COMMAND_TIMEOUT_SECONDS)
