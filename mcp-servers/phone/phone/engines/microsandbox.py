"""The phone as one microsandbox microVM, run through the microsandbox SDK."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass

from microsandbox import (
    Action,
    DestGroup,
    Destination,
    ExecTimeoutError,
    MicrosandboxError,
    Network,
    NetworkPolicy,
    Rule,
    SandboxNotFoundError,
    SandboxStatus,
)

from phone.engines.microsandbox_sdk import (
    ImageConfig,
    Images,
    RunningSandbox,
    SandboxConfig,
    Sandboxes,
    StoredSandbox,
    sandbox_config,
)
from phone.models.command import COMMAND_TIMEOUT_SECONDS, CommandResult
from phone.models.errors import EngineError, EngineTimeout
from phone.models.phone import LABEL, PhoneSpec, PhoneState, Program

CREATE_TIMEOUT_SECONDS = 300.0
MEMORY_MIB = 2048
CPUS = 2


def phone_network_policy() -> NetworkPolicy:
    """DNS and public addresses only: never the Mac, its loopback, or the person's own network."""
    return NetworkPolicy(
        default_egress=Action.DENY,
        default_ingress=Action.ALLOW,
        rules=(*Rule.allow_dns(), Rule.allow(destination=Destination.group(DestGroup.PUBLIC))),
    )


class SandboxMissing(EngineError):
    """microsandbox knows no VM by that name."""


def image_command(config: ImageConfig | None) -> Program:
    """The image's own entrypoint and command, which a microVM does not run by itself."""
    argv = () if config is None else (*(config.entrypoint or ()), *(config.cmd or ()))
    if not argv:
        raise EngineError("The phone's image has no command to start it with.")
    return Program(argv=argv, env={})


def state_of(status: SandboxStatus) -> PhoneState:
    return "running" if status == SandboxStatus.RUNNING else "stopped"


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
    """The phone as one detached microVM, so it outlives this server."""

    sandboxes: Sandboxes
    images: Images

    async def create(self, spec: PhoneSpec) -> None:
        made = self.sandboxes.create(
            spec.name,
            image=spec.image,
            memory=MEMORY_MIB,
            cpus=CPUS,
            labels={LABEL: spec.name},
            network=Network(policy=phone_network_policy()),
            detached=True,
        )
        await sdk_answer("create", made, CREATE_TIMEOUT_SECONDS)
        await self._run_image_command(spec.name)

    async def start(self, name: str) -> None:
        started = self.sandboxes.start(name, detached=True)
        await sdk_answer("start", started, COMMAND_TIMEOUT_SECONDS)
        await self._run_image_command(name)

    async def state(self, name: str) -> PhoneState:
        try:
            stored = await self._stored("get", name)
        except SandboxMissing:
            return "missing"
        return state_of(stored.status)

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
        await self.launch(name, image_command(detail.config))

    async def _stored(self, action: str, name: str) -> StoredSandbox:
        return await sdk_answer(action, self.sandboxes.get(name), COMMAND_TIMEOUT_SECONDS)

    async def _config(self, name: str) -> SandboxConfig:
        return sandbox_config((await self._stored("get", name)).config_json)

    async def _running(self, name: str) -> RunningSandbox:
        stored = await self._stored("exec", name)
        return await sdk_answer("exec", stored.connect(), COMMAND_TIMEOUT_SECONDS)
