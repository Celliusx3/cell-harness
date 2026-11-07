"""Fakes. Hermetic: docker is a recorder that answers from a script, and time is a dial."""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from mcp.server import MCPServer

from computer.clock import Clock
from computer.config import Config
from computer.models.command import CommandResult
from computer.models.errors import EngineError
from computer.services.host_services import PreparedHostService, command_variables

NAME = "cell-harness-computer"
IMAGE = (
    "ghcr.io/celliusx3/cell-harness/pc"
    "@sha256:50c6c9f7c0aad1fb369f44d532a3c19f62c732a08f12b953b44664f3af21e9e3"
)
IDLE_SECONDS = 600
API_HOST_PORT = 62477
GATEWAY_HOST_PORT = 62480
EPOCH = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
FILES_DIR = Path("/tmp/cell-harness-files")
SKILLS_DIR = Path("/tmp/cell-harness-skills")
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
SCREENSHOT = CommandResult(0, base64.b64encode(PNG).decode(), "")

NAVIGATED = json.dumps({"ok": True, "url": "https://example.com/", "title": "Example Domain"})
SNAPSHOT = json.dumps(
    {
        "ok": True,
        "url": "https://example.com/",
        "title": "Example Domain",
        "elements": [{"ref": "eb52dcaf9e50e408fcfcb5957b1457dc0", "role": "link"}],
        "tree": 'Example Domain\n- link "Learn more" [eb52dcaf9e50e408fcfcb5957b1457dc0]',
    }
)
ACTED = json.dumps({**json.loads(SNAPSHOT), "completed": 2})
STALE_REF_REPLY = json.dumps(
    {
        "ok": False,
        "completed": 0,
        "uncertain": False,
        "error": "Stale element ref. Take a fresh snapshot.",
        "fallback": "computer_act",
    }
)
CDP_DOWN = json.dumps(
    {
        "ok": False,
        "error": "CDP not ready on port 9222: <urlopen error [Errno 111] Connection refused>",
        "fallback": "computer_act",
        "uncertain": False,
    }
)


def config(
    idle_minutes: int = IDLE_SECONDS // 60,
    *,
    files_dir: Path = FILES_DIR,
    skills_dirs: tuple[Path, ...] = (SKILLS_DIR,),
) -> Config:
    return Config(
        engine="docker",
        image=IMAGE,
        container_name=NAME,
        idle_minutes=idle_minutes,
        files_dir=files_dir,
        skills_dirs=skills_dirs,
    )


def mount_of(volume: str) -> dict[str, object]:
    """A `-v` argument as `docker inspect` prints the mount it makes."""
    source, destination, *mode = volume.split(":")
    kind = "bind" if source.startswith("/") else "volume"
    return {"Type": kind, "Source": source, "Destination": destination, "RW": mode != ["ro"]}


MOUNTED = [
    mount_of(f"{NAME}-home:/home/pc"),
    mount_of(f"{FILES_DIR}:{FILES_DIR}"),
    mount_of(f"{SKILLS_DIR}:{SKILLS_DIR}:ro"),
]


class FakeDocker:
    """Records every command; plays a container whose status the commands change."""

    def __init__(self, *, status: str, page_replies: Sequence[str] = (NAVIGATED,)) -> None:
        self.status = status
        self.page_replies = list(page_replies)
        self.calls: list[list[str]] = []
        self.stdins: list[str] = []
        self.timeouts: list[float] = []
        self.refused_verbs: set[str] = set()
        self.gates: dict[str, asyncio.Event] = {}
        self.unreachable = False
        self.api_host_port = API_HOST_PORT
        self.gateway_host_port = GATEWAY_HOST_PORT
        self.bindings: dict[str, object] | None = {
            "6080/tcp": [{"HostIp": "127.0.0.1", "HostPort": ""}],
        }
        self.raw_bindings: str | None = None
        self.mounts: list[dict[str, object]] = list(MOUNTED)
        self.python_result = CommandResult(0, "", "")
        self.screenshot = SCREENSHOT

    async def run(
        self, args: Sequence[str], *, stdin: str, timeout_seconds: float
    ) -> CommandResult:
        self.calls.append(list(args))
        self.stdins.append(stdin)
        self.timeouts.append(timeout_seconds)
        await asyncio.sleep(0)
        if self.unreachable:
            raise EngineError("docker is not on PATH: install Docker and start it")
        if args[0] in self.gates:
            await self.gates[args[0]].wait()
        if args[0] in self.refused_verbs:
            return CommandResult(returncode=1, stdout="", stderr=f"Error: {args[0]} refused")
        return self._answer(args)

    def _answer(self, args: Sequence[str]) -> CommandResult:
        verb = args[0]
        if verb == "inspect" and self.status == "missing":
            return CommandResult(1, "", f"Error response from daemon: No such container: {NAME}\n")
        if verb == "inspect" and "{{json .HostConfig.PortBindings}}" in args:
            return CommandResult(0, (self.raw_bindings or json.dumps(self.bindings)) + "\n", "")
        if verb == "inspect" and "{{json .Mounts}}" in args:
            return CommandResult(0, json.dumps(self.mounts) + "\n", "")
        if verb == "inspect":
            return CommandResult(0, f"{self.status}\n", "")
        if verb == "port":
            published = self.gateway_host_port if args[2] == "6080" else self.api_host_port
            return CommandResult(0, f"127.0.0.1:{published}\n", "")
        if verb == "rm":
            self.status = "missing"
        if verb == "run":
            published = [
                args[at + 1].rsplit(":", 1)[1] for at, arg in enumerate(args) if arg == "-p"
            ]
            self.bindings = {f"{port}/tcp": [{"HostIp": "127.0.0.1"}] for port in published}
            self.mounts = [mount_of(args[at + 1]) for at, arg in enumerate(args) if arg == "-v"]
        if verb == "start":
            self.api_host_port += 1
        if verb in ("run", "start"):
            self.status = "running"
        if verb == "stop":
            self.status = "exited"
        if verb == "exec" and any("scrot" in arg for arg in args):
            return self.screenshot
        if verb == "exec" and "bash" in args:
            return CommandResult(0, "", "")
        if verb == "exec" and "python3" in args:
            return self.python_result
        if verb == "exec" and "-d" not in args:
            reply = (
                self.page_replies[0] if len(self.page_replies) == 1 else self.page_replies.pop(0)
            )
            return CommandResult(0, reply + "\n", "")
        return CommandResult(0, "", "")

    def verbs(self) -> list[str]:
        return [call[0] for call in self.calls]

    def launches(self) -> list[list[str]]:
        return [call for call in self.calls if call[:2] == ["exec", "-d"]]

    def scripts(self) -> list[str]:
        return [call[-1] for call in self.calls if call[:4] == ["exec", NAME, "bash", "-c"]]


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


class TickingClock:
    """Time that jumps forward by whatever is slept."""

    def __init__(self) -> None:
        self.now = 0.0
        self.clock = Clock(
            now=lambda: self.now, sleep=self.sleep, wall=lambda: EPOCH + timedelta(seconds=self.now)
        )

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        await asyncio.sleep(0)


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


def server_with(
    docker: FakeDocker,
    dial: Dial | None = None,
    host_services: Sequence[PreparedHostService] = (),
) -> MCPServer:
    from computer.engines.docker import DockerEngine
    from computer.server import build
    from computer.services.browser import Browser
    from computer.services.desktop import Desktop
    from computer.services.files import Files
    from computer.services.live_screen import LiveScreen
    from computer.services.machine import Machine
    from computer.services.shell import Shell
    from computer.tools import Computer

    clock = (dial or Dial()).clock
    engine = DockerEngine(docker=docker)
    machine = Machine(engine=engine, config=config(), clock=clock, host_service_ports=())
    return build(
        Computer(
            machine=machine,
            browser=Browser(engine=engine, container=NAME, clock=TickingClock().clock),
            desktop=Desktop(engine=engine, container=NAME),
            live_screen=LiveScreen(engine=engine, container=NAME, machine=machine, clock=clock),
            files=Files(engine=engine, container=NAME),
            shell=Shell(
                engine=engine,
                container=NAME,
                clock=TickingClock().clock,
                variables=command_variables(host_services, engine.host_address),
            ),
        ),
        host_services,
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
