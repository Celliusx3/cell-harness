"""What every tool reaches: the phone, and one call's hold on it."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ImageContent

from phone.clock import Clock
from phone.models.errors import EngineError
from phone.services.apps import AppError, Apps
from phone.services.machine import Machine
from phone.services.screen import Screen, ScreenError
from phone.services.touch import Touch, TouchError

SETTLE_SECONDS = 0.5


@dataclass(frozen=True)
class Phone:
    """What the tools reach: the machine, its screen, its apps and its input."""

    machine: Machine
    screen: Screen
    apps: Apps
    touch: Touch
    clock: Clock


@asynccontextmanager
async def phone_for_one_call(machine: Machine) -> AsyncIterator[None]:
    """The booted phone for one call, its failures put in words the model can act on."""
    try:
        async with machine.in_use():
            yield
    except EngineError as err:
        raise ToolError(f"The phone is not available: {err}") from err
    except (ScreenError, AppError, TouchError) as err:
        raise ToolError(str(err)) from err


async def screen_now(phone: Phone) -> ImageContent:
    """The phone's screen as it is now."""
    shot = await phone.screen.screenshot()
    return ImageContent(type="image", data=shot.image, mime_type=shot.mime_type)


async def screen_after_action(phone: Phone) -> ImageContent:
    """The phone's screen once an action has had a moment to show."""
    await phone.clock.sleep(SETTLE_SECONDS)
    return await screen_now(phone)
