"""What every tool reaches: the computer, one call's hold on it, and the preview's address."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.mcpserver.exceptions import ToolError

from computer.browser import Browser, BrowserError
from computer.desktop import Desktop, DesktopError
from computer.docker import DockerError
from computer.files import Files, FilesError
from computer.live_screen import LiveScreen
from computer.machine import Machine

PREVIEW_URI = "ui://computer/screen"


@dataclass(frozen=True)
class Computer:
    """What the tools reach: the machine, its Chrome, its screenshots, live screen and files."""

    machine: Machine
    browser: Browser
    desktop: Desktop
    live_screen: LiveScreen
    files: Files


@asynccontextmanager
async def computer_for_one_call(machine: Machine) -> AsyncIterator[None]:
    """The running computer for one call, its failures put in words the model can act on."""
    try:
        async with machine.in_use():
            yield
    except DockerError as err:
        raise ToolError(f"The computer is not available: {err}") from err
    except (BrowserError, DesktopError, FilesError) as err:
        raise ToolError(str(err)) from err
