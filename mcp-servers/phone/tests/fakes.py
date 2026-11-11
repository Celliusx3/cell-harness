"""Fakes. Hermetic: the engine is a recorder that plays a phone, and time moves only by sleeping."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mcp.server import MCPServer

from phone.clock import Clock
from phone.config import Config
from phone.models.command import CommandResult
from phone.models.phone import PhoneSpec, PhoneState, Program
from phone.server import build
from phone.services.apps import LIST_PACKAGES, Apps
from phone.services.live_screen import SCREEN_PROGRAM, LiveScreen
from phone.services.machine import BOOT_COMPLETED, GATEWAY_PORT, Machine
from phone.services.screen import SCREENSHOT, Screen
from phone.services.touch import Touch
from phone.tools import Phone

NAME = "cell-harness-phone"
IMAGE = "ghcr.io/celliusx3/cell-harness/phone@sha256:" + "0" * 64
KERNEL = Path("/opt/cell-harness/libkrunfw.5.dylib")
FILES_DIR = Path("/tmp/cell-harness-files")
INSTALL = "base64 -d | pm install"
INSTALLED_RESULT = CommandResult(0, "Success\n", "")
BOOT_POLLS = 2
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
SCREENSHOT_RESULT = CommandResult(0, base64.b64encode(PNG).decode() + "\n", "")
CONFIG = Config(image=IMAGE, name=NAME, kernel=KERNEL, files_dir=FILES_DIR, idle_minutes=10)
IDLE_SECONDS = CONFIG.idle_minutes * 60
GATEWAY_HOST_PORT = 49152
EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


class FakeEngine:
    """A phone that boots after `boot_polls_needed` looks, shows `screen`, and records commands.

    A `pm install` adds `installs` to its third-party packages; `answers` gives a command's
    result in place of the phone's own. `phone-screen` programs are recorded apart, and a phone
    with a `replacement` reason is one made to another shape.
    """

    def __init__(
        self,
        state: PhoneState,
        *,
        installs: str | None = None,
        boot_polls_needed: int = BOOT_POLLS,
        screen: CommandResult = SCREENSHOT_RESULT,
        packages: frozenset[str] = frozenset(),
        answers: Mapping[str, CommandResult] | None = None,
        replacement: str | None = None,
    ) -> None:
        self.phone_state: PhoneState = state
        self.installs = installs
        self.boot_polls_needed = boot_polls_needed
        self.screen = screen
        self.packages = packages
        self.answers: Mapping[str, CommandResult] = answers or {}
        self.replacement = replacement
        self.removed = 0
        self.created = 0
        self.started = 0
        self.stopped = 0
        self.boot_polls = 0
        self.specs: list[PhoneSpec] = []
        self.commands: list[str] = []
        self.stdins: list[str | None] = []
        self.timeouts: list[float] = []
        self.screen_commands: list[str] = []

    async def create(self, spec: PhoneSpec) -> None:
        self.specs.append(spec)
        self.created += 1
        self.phone_state = "running"

    async def start(self, name: str) -> None:
        self.started += 1
        self.phone_state = "running"

    async def stop(self, name: str) -> None:
        self.stopped += 1
        self.phone_state = "stopped"

    async def remove(self, name: str) -> None:
        self.removed += 1
        self.phone_state = "missing"

    async def state(self, name: str) -> PhoneState:
        return self.phone_state

    async def replacement_reason(self, spec: PhoneSpec) -> str | None:
        return self.replacement

    async def host_port(self, name: str, guest_port: int) -> int:
        assert guest_port == GATEWAY_PORT
        return GATEWAY_HOST_PORT

    async def run(
        self, name: str, program: Program, *, stdin: str | None, timeout_seconds: float
    ) -> CommandResult:
        if program == BOOT_COMPLETED:
            self.boot_polls += 1
            booted = self.boot_polls >= self.boot_polls_needed
            return CommandResult(0, "1\n" if booted else "0\n", "")
        if program == SCREENSHOT:
            return self.screen
        if program.argv[0] == SCREEN_PROGRAM:
            self.screen_commands.append(" ".join(program.argv))
            return CommandResult(0, "", "")
        helper, command = program.argv
        assert (helper, program.env) == ("android", {})
        self.commands.append(command)
        self.stdins.append(stdin)
        self.timeouts.append(timeout_seconds)
        return self.answers.get(command) or self._answer(command)

    def _answer(self, command: str) -> CommandResult:
        if command == LIST_PACKAGES:
            listed = "".join(f"package:{package}\n" for package in sorted(self.packages))
            return CommandResult(0, listed, "")
        if command.startswith(INSTALL):
            self.packages = self.packages | {self.installs} if self.installs else self.packages
            return INSTALLED_RESULT
        return CommandResult(0, "", "")

    async def launch(self, name: str, program: Program) -> CommandResult:
        raise AssertionError(f"the fake phone launches nothing: {program.argv}")


class Ticking:
    """Time that jumps forward by whatever is slept, so no test waits; the idle stop never comes."""

    def __init__(self) -> None:
        self.now = 0.0
        self.clock = Clock(now=lambda: self.now, sleep=self.sleep, wall=self.wall)

    def wall(self) -> datetime:
        return EPOCH + timedelta(seconds=self.now)

    async def sleep(self, seconds: float) -> None:
        if seconds >= IDLE_SECONDS:
            await asyncio.Event().wait()
        self.now += seconds
        await asyncio.sleep(0)


class Dial:
    """Time that moves only when a test turns it."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleepers: list[tuple[float, asyncio.Future[None]]] = []
        self.clock = Clock(now=lambda: self.now, sleep=self.sleep, wall=self.wall)

    def wall(self) -> datetime:
        return EPOCH + timedelta(seconds=self.now)

    async def sleep(self, seconds: float) -> None:
        wake: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self.sleepers.append((self.now + seconds, wake))
        await wake

    async def turn(self, seconds: float) -> None:
        await settle()
        self.now += seconds
        for at, wake in self.sleepers:
            if at <= self.now and not wake.done():
                wake.set_result(None)
        await settle()


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


def machine_over(engine: FakeEngine, clock: Clock | None = None) -> Machine:
    return Machine(engine=engine, config=CONFIG, clock=Ticking().clock if clock is None else clock)


def phone_over(engine: FakeEngine, *, files_dir: Path, clock: Clock) -> Phone:
    machine = Machine(engine=engine, config=CONFIG, clock=clock)
    return Phone(
        machine=machine,
        screen=Screen(engine=engine, name=NAME),
        apps=Apps(engine=engine, name=NAME, files_dir=files_dir),
        touch=Touch(engine=engine, name=NAME),
        live_screen=LiveScreen(engine=engine, name=NAME, machine=machine, clock=clock),
        clock=clock,
    )


def phone_server(
    engine: FakeEngine, *, files_dir: Path = FILES_DIR, clock: Clock | None = None
) -> MCPServer:
    return build(
        phone_over(engine, files_dir=files_dir, clock=Ticking().clock if clock is None else clock)
    )
