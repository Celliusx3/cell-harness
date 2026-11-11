"""The part of the microsandbox SDK the engine calls, and the VM config it reads back."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from microsandbox import MountConfig, Network, SandboxStatus
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from phone.models.errors import EngineError


class ExecResult(Protocol):
    @property
    def exit_code(self) -> int: ...

    @property
    def stdout_text(self) -> str: ...

    @property
    def stderr_text(self) -> str: ...


class DetachedJob(Protocol):
    @property
    def id(self) -> str: ...


class RunningSandbox(Protocol):
    """A connection to a running VM, as `SandboxHandle.connect` returns it."""

    async def exec(
        self,
        cmd: str,
        args: list[str],
        *,
        env: Mapping[str, str],
        timeout: float | None,
        stdin: bytes | None,
    ) -> ExecResult: ...

    async def exec_detached(
        self, cmd: str, args: list[str], *, env: Mapping[str, str]
    ) -> DetachedJob: ...


class StoredSandbox(Protocol):
    """A VM microsandbox knows by name, running or not, as `Sandbox.get` returns it."""

    @property
    def status(self) -> SandboxStatus: ...

    @property
    def config_json(self) -> str: ...

    async def connect(self) -> RunningSandbox: ...

    async def stop(self) -> None: ...


class Sandboxes(Protocol):
    """The lifecycle calls of `microsandbox.Sandbox`, the SDK's entry point."""

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
    ) -> RunningSandbox: ...

    async def start(self, name: str, *, detached: bool) -> RunningSandbox: ...

    async def get(self, name: str) -> StoredSandbox: ...


class ImageConfig(Protocol):
    @property
    def entrypoint(self) -> list[str] | None: ...

    @property
    def cmd(self) -> list[str] | None: ...


class ImageDetail(Protocol):
    @property
    def config(self) -> ImageConfig | None: ...


class Images(Protocol):
    """`microsandbox.Image`'s lookup of a pulled image's own config."""

    async def inspect(self, reference: str) -> ImageDetail: ...


class OciImage(BaseModel):
    model_config = ConfigDict(frozen=True)

    reference: str


class StoredImage(BaseModel):
    model_config = ConfigDict(frozen=True)

    oci: OciImage = Field(alias="Oci")


class SandboxConfig(BaseModel):
    """The fields of a VM's stored config the engine reads, in microsandbox's names."""

    model_config = ConfigDict(frozen=True)

    image: StoredImage


def sandbox_config(config_json: str) -> SandboxConfig:
    try:
        return SandboxConfig.model_validate_json(config_json)
    except ValidationError as err:
        raise EngineError(
            "microsandbox answered the phone's config with something this server cannot read"
        ) from err
