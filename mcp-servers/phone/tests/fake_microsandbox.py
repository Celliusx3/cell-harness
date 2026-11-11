"""A fake of the microsandbox SDK surface the engine uses: VMs as records, no VM booted."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from microsandbox import (
    ExecTimeoutError,
    MicrosandboxError,
    MountConfig,
    Network,
    SandboxNotFoundError,
    SandboxStatus,
)


@dataclass(frozen=True)
class CreateCall:
    """The arguments one `Sandbox.create` was called with."""

    name: str
    image: str
    memory: int
    cpus: int
    labels: Mapping[str, str]
    volumes: Mapping[str, MountConfig]
    network: Network
    detached: bool


@dataclass(frozen=True)
class ExecCall:
    cmd: str
    args: list[str]
    env: Mapping[str, str]
    timeout: float | None
    stdin: bytes | None


@dataclass(frozen=True)
class FakeExecOutput:
    exit_code: int
    stdout_text: str
    stderr_text: str


@dataclass(frozen=True)
class FakeJob:
    id: str


@dataclass(frozen=True)
class FakeImageConfig:
    entrypoint: list[str] | None
    cmd: list[str] | None


@dataclass(frozen=True)
class FakeImageDetail:
    config: FakeImageConfig | None


@dataclass
class FakeImages:
    """`microsandbox.Image.inspect` over one image whose command is given."""

    entrypoint: list[str] | None = None
    cmd: list[str] | None = field(default_factory=lambda: ["/usr/local/bin/phone-start"])
    inspected: list[str] = field(default_factory=list)

    async def inspect(self, reference: str) -> FakeImageDetail:
        self.inspected.append(reference)
        return FakeImageDetail(FakeImageConfig(self.entrypoint, self.cmd))


@dataclass
class FakeRunningSandbox:
    """A connection to one VM: records each program run in it, answers from a script."""

    vms: FakeSandboxes

    async def exec(
        self,
        cmd: str,
        args: list[str],
        *,
        env: Mapping[str, str],
        timeout: float | None,
        stdin: bytes | None,
    ) -> FakeExecOutput:
        self.vms.execs.append(ExecCall(cmd, args, env, timeout, stdin))
        if self.vms.exec_hangs:
            await asyncio.Event().wait()
        if self.vms.exec_times_out:
            raise ExecTimeoutError("exec timed out")
        if self.vms.exec_refusal is not None:
            raise self.vms.exec_refusal
        return self.vms.exec_output

    async def exec_detached(self, cmd: str, args: list[str], *, env: Mapping[str, str]) -> FakeJob:
        self.vms.launches.append(ExecCall(cmd, args, env, None, None))
        return FakeJob(id="job-1")


@dataclass
class FakeStoredSandbox:
    vms: FakeSandboxes
    status: SandboxStatus
    image: str

    @property
    def config_json(self) -> str:
        return self.vms.raw_config or json.dumps({"image": {"Oci": {"reference": self.image}}})

    async def connect(self) -> FakeRunningSandbox:
        return FakeRunningSandbox(self.vms)

    async def stop(self) -> None:
        self.vms.calls.append("stop")
        self.status = SandboxStatus.STOPPED


@dataclass
class FakeSandboxes:
    """`microsandbox.Sandbox`'s lifecycle calls over a table of VMs."""

    stored: dict[str, FakeStoredSandbox] = field(default_factory=dict)
    created: list[CreateCall] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    execs: list[ExecCall] = field(default_factory=list)
    launches: list[ExecCall] = field(default_factory=list)
    exec_output: FakeExecOutput = FakeExecOutput(0, "", "")
    exec_times_out: bool = False
    exec_hangs: bool = False
    exec_refusal: MicrosandboxError | None = None
    raw_config: str | None = None

    async def create(
        self,
        name: str,
        *,
        image: str,
        memory: int,
        cpus: int,
        labels: Mapping[str, str],
        volumes: Mapping[str, MountConfig],
        network: Network,
        detached: bool,
    ) -> FakeRunningSandbox:
        self.calls.append("create")
        self.created.append(
            CreateCall(name, image, memory, cpus, labels, volumes, network, detached)
        )
        self.stored[name] = FakeStoredSandbox(self, SandboxStatus.RUNNING, image)
        return FakeRunningSandbox(self)

    async def start(self, name: str, *, detached: bool) -> FakeRunningSandbox:
        self.calls.append(f"start detached={detached}")
        (await self.get(name)).status = SandboxStatus.RUNNING
        return FakeRunningSandbox(self)

    async def get(self, name: str) -> FakeStoredSandbox:
        if name not in self.stored:
            raise SandboxNotFoundError(f"sandbox not found: {name}")
        return self.stored[name]
