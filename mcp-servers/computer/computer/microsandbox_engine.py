"""The PC as one microsandbox microVM, run through the microsandbox SDK."""

from __future__ import annotations

import asyncio
import hashlib
import json
import socket
from collections.abc import Awaitable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass

from microsandbox import (
    ExecTimeoutError,
    MicrosandboxError,
    MountConfig,
    NamedVolumeMode,
    PortBinding,
    SandboxNotFoundError,
    SandboxStatus,
    Volume,
)

from computer.command import (
    COMMAND_TIMEOUT_SECONDS,
    CommandResult,
    EngineError,
    EngineTimeout,
    stdout_of,
)
from computer.engine import LABEL, LOOPBACK, PcSpec, PcState, Program
from computer.microsandbox_sdk import (
    ImageConfig,
    Images,
    RunningSandbox,
    SandboxConfig,
    Sandboxes,
    StoredSandbox,
    sandbox_config,
)

CREATE_TIMEOUT_SECONDS = 300.0
MEMORY_MIB = 2048
CPUS = 2
SHM_PATH = "/dev/shm"
SHAPE_LABEL = "cell-harness.computer.shape"
REPLACEMENT_REASON = "its published ports or shared folders are not the spec's"
STOPPED_STATUSES = frozenset({SandboxStatus.STOPPED, SandboxStatus.CRASHED, SandboxStatus.CREATED})
# Named in the bundled msb runtime's guest setup; not yet checked from a running PC.
HOST_FROM_THE_PC = "host.microsandbox.internal"


class SandboxMissing(EngineError):
    """microsandbox knows no VM by that name."""


def shape_fingerprint(spec: PcSpec) -> str:
    """A digest of the spec's published ports and shared folders, the parts a VM is made with."""
    shape = {
        "ports": sorted(spec.published_ports),
        "folders": sorted([str(folder.path), folder.writable] for folder in spec.shared_folders),
    }
    return hashlib.sha256(json.dumps(shape).encode()).hexdigest()


def sandbox_labels(spec: PcSpec) -> dict[str, str]:
    return {LABEL: spec.name, SHAPE_LABEL: shape_fingerprint(spec)}


def sandbox_volumes(spec: PcSpec) -> dict[str, MountConfig]:
    """The home as a named volume, each shared folder at its own path, and shm as a tmpfs."""
    home = Volume.named(spec.home.name, mode=NamedVolumeMode.ENSURE_EXISTS)
    shared = {
        str(folder.path): Volume.bind(str(folder.path), readonly=not folder.writable)
        for folder in spec.shared_folders
    }
    return {
        spec.home.guest_path: home,
        **shared,
        SHM_PATH: Volume.tmpfs(size_mib=spec.shm_megabytes),
    }


def port_bindings(host_ports: Mapping[int, int]) -> list[PortBinding]:
    """Each guest port, keyed to its host port, published on loopback only."""
    return [
        PortBinding.tcp(host_port, guest_port, bind=LOOPBACK)
        for guest_port, host_port in host_ports.items()
    ]


def free_loopback_ports(count: int) -> tuple[int, ...]:
    """`count` distinct loopback ports nothing listens on right now."""
    with ExitStack() as stack:
        sockets = [stack.enter_context(socket.socket()) for _ in range(count)]
        for sock in sockets:
            sock.bind((LOOPBACK, 0))
        return tuple(sock.getsockname()[1] for sock in sockets)


def image_command(config: ImageConfig | None) -> Program:
    """The image's own entrypoint and command, which a microVM does not run by itself."""
    argv = () if config is None else (*(config.entrypoint or ()), *(config.cmd or ()))
    if not argv:
        raise EngineError("The computer's image has no command to start it with.")
    return Program(argv=argv, env={})


def state_of(status: SandboxStatus) -> PcState:
    return "running" if status == SandboxStatus.RUNNING else "stopped"


def loopback_port(config: SandboxConfig, guest_port: int) -> int:
    """The host port a guest port is published on, refused unless it is loopback."""
    for port in config.network.ports:
        if port.guest_port == guest_port and port.host_bind == LOOPBACK:
            return port.host_port
    raise EngineError(f"The computer's port {guest_port} is not published on {LOOPBACK}.")


def replacement_reason(config: SandboxConfig, spec: PcSpec) -> str | None:
    """Why a VM made with `config` is not the spec's, read from the shape label it was made with."""
    if config.labels.get(SHAPE_LABEL) == shape_fingerprint(spec):
        return None
    return REPLACEMENT_REASON


async def sdk_answer[T](action: str, call: Awaitable[T], timeout_seconds: float) -> T:
    """`call`'s answer, with every microsandbox failure and a missed deadline an EngineError."""
    try:
        async with asyncio.timeout(timeout_seconds):
            return await call
    except (TimeoutError, ExecTimeoutError) as err:
        raise EngineTimeout(
            f"microsandbox {action} did not finish within {timeout_seconds:g} seconds"
        ) from err
    except SandboxNotFoundError as err:
        raise SandboxMissing(f"microsandbox {action} failed: {err}") from err
    except MicrosandboxError as err:
        raise EngineError(f"microsandbox {action} failed: {err}") from err


@dataclass(frozen=True)
class MicrosandboxEngine:
    """The PC as one detached microVM, so it outlives this server and is adopted at startup."""

    sandboxes: Sandboxes
    images: Images

    @property
    def host_address(self) -> str:
        return HOST_FROM_THE_PC

    async def create(self, spec: PcSpec) -> None:
        ports = spec.published_ports
        host_ports = dict(zip(ports, free_loopback_ports(len(ports)), strict=True))
        made = self.sandboxes.create(
            spec.name,
            image=spec.image,
            memory=MEMORY_MIB,
            cpus=CPUS,
            env=dict(spec.env),
            labels=sandbox_labels(spec),
            volumes=sandbox_volumes(spec),
            ports=port_bindings(host_ports),
            detached=True,
        )
        await sdk_answer("create", made, CREATE_TIMEOUT_SECONDS)
        await self._run_image_command(spec.name)

    async def start(self, name: str) -> None:
        started = self.sandboxes.start(name, detached=True)
        await sdk_answer("start", started, COMMAND_TIMEOUT_SECONDS)
        await self._run_image_command(name)

    async def stop(self, name: str) -> None:
        stored = await self._stored("stop", name)
        await sdk_answer("stop", stored.stop(), COMMAND_TIMEOUT_SECONDS)

    async def remove(self, name: str) -> None:
        stored = await self._stored("remove", name)
        if stored.status not in STOPPED_STATUSES:
            await sdk_answer("remove", stored.stop(), COMMAND_TIMEOUT_SECONDS)
        await sdk_answer("remove", self.sandboxes.remove(name), COMMAND_TIMEOUT_SECONDS)

    async def state(self, name: str) -> PcState:
        try:
            stored = await self._stored("get", name)
        except SandboxMissing:
            return "missing"
        return state_of(stored.status)

    async def replacement_reason(self, spec: PcSpec) -> str | None:
        return replacement_reason(await self._config(spec.name), spec)

    async def host_port(self, name: str, guest_port: int) -> int:
        return loopback_port(await self._config(name), guest_port)

    async def environment(self, name: str) -> dict[str, str]:
        return {entry.key: entry.value for entry in (await self._config(name)).env}

    async def run(
        self, name: str, program: Program, *, stdin: str | None, timeout_seconds: float
    ) -> CommandResult:
        running = await self._running(name)
        cmd, *args = program.argv
        output = await sdk_answer(
            "exec",
            running.exec(
                cmd,
                args,
                env=dict(program.env),
                timeout=timeout_seconds,
                stdin=None if stdin is None else stdin.encode(),
            ),
            timeout_seconds,
        )
        return CommandResult(output.exit_code, output.stdout_text, output.stderr_text)

    async def launch(self, name: str, program: Program) -> CommandResult:
        running = await self._running(name)
        cmd, *args = program.argv
        launched = running.exec_detached(cmd, args, env=dict(program.env))
        await sdk_answer("exec", launched, COMMAND_TIMEOUT_SECONDS)
        return CommandResult(0, "", "")

    async def _run_image_command(self, name: str) -> None:
        reference = (await self._config(name)).image.oci.reference
        detail = await sdk_answer(
            "inspect", self.images.inspect(reference), COMMAND_TIMEOUT_SECONDS
        )
        launched = await self.launch(name, image_command(detail.config))
        stdout_of(launched, "starting the computer's desktop")

    async def _stored(self, action: str, name: str) -> StoredSandbox:
        return await sdk_answer(action, self.sandboxes.get(name), COMMAND_TIMEOUT_SECONDS)

    async def _config(self, name: str) -> SandboxConfig:
        return sandbox_config((await self._stored("get", name)).config_json)

    async def _running(self, name: str) -> RunningSandbox:
        stored = await self._stored("exec", name)
        return await sdk_answer("exec", stored.connect(), COMMAND_TIMEOUT_SECONDS)
