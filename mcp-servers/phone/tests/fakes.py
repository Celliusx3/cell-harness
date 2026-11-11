"""Fakes. Hermetic: the engine is a recorder that plays a phone, and time moves only by sleeping."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from mcp.server import MCPServer

from phone.clock import Clock
from phone.config import Config
from phone.models.command import CommandResult
from phone.models.phone import PhoneSpec, PhoneState, Program
from phone.server import build
from phone.services.machine import BOOT_COMPLETED, Machine
from phone.services.screen import SCREENSHOT, Screen
from phone.tools import Phone

NAME = "cell-harness-phone"
IMAGE = "ghcr.io/celliusx3/cell-harness/phone@sha256:" + "0" * 64
KERNEL = Path("/opt/cell-harness/libkrunfw.5.dylib")
BOOT_POLLS = 2
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
SCREENSHOT_RESULT = CommandResult(0, base64.b64encode(PNG).decode() + "\n", "")
CONFIG = Config(image=IMAGE, name=NAME, kernel=KERNEL)


class FakeEngine:
    """A phone that boots after `boot_polls_needed` looks, and shows `screen` when asked."""

    def __init__(
        self,
        state: PhoneState,
        *,
        boot_polls_needed: int = BOOT_POLLS,
        screen: CommandResult = SCREENSHOT_RESULT,
    ) -> None:
        self.phone_state: PhoneState = state
        self.boot_polls_needed = boot_polls_needed
        self.screen = screen
        self.created = 0
        self.started = 0
        self.boot_polls = 0
        self.specs: list[PhoneSpec] = []

    async def create(self, spec: PhoneSpec) -> None:
        self.specs.append(spec)
        self.created += 1
        self.phone_state = "running"

    async def start(self, name: str) -> None:
        self.started += 1
        self.phone_state = "running"

    async def state(self, name: str) -> PhoneState:
        return self.phone_state

    async def run(
        self, name: str, program: Program, *, stdin: str | None, timeout_seconds: float
    ) -> CommandResult:
        if program == BOOT_COMPLETED:
            self.boot_polls += 1
            booted = self.boot_polls >= self.boot_polls_needed
            return CommandResult(0, "1\n" if booted else "0\n", "")
        if program == SCREENSHOT:
            return self.screen
        raise AssertionError(f"the fake phone does not know {program.argv}")

    async def launch(self, name: str, program: Program) -> CommandResult:
        raise AssertionError(f"the fake phone launches nothing: {program.argv}")


class Ticking:
    """Time that jumps forward by whatever is slept, so no test waits."""

    def __init__(self) -> None:
        self.now = 0.0
        self.clock = Clock(now=lambda: self.now, sleep=self.sleep)

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        await asyncio.sleep(0)


def machine_over(engine: FakeEngine) -> Machine:
    return Machine(engine=engine, config=CONFIG, clock=Ticking().clock)


def phone_server(engine: FakeEngine) -> MCPServer:
    return build(Phone(machine=machine_over(engine), screen=Screen(engine=engine, name=NAME)))
