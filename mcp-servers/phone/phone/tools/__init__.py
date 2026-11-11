"""What every tool reaches: the phone, and one call's hold on it."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.mcpserver.exceptions import ToolError

from phone.models.errors import EngineError
from phone.services.machine import Machine
from phone.services.screen import Screen, ScreenError


@dataclass(frozen=True)
class Phone:
    """What the tools reach: the machine and its screen."""

    machine: Machine
    screen: Screen


@asynccontextmanager
async def phone_for_one_call(machine: Machine) -> AsyncIterator[None]:
    """The booted phone for one call, its failures put in words the model can act on."""
    try:
        async with machine.in_use():
            yield
    except EngineError as err:
        raise ToolError(f"The phone is not available: {err}") from err
    except ScreenError as err:
        raise ToolError(str(err)) from err
