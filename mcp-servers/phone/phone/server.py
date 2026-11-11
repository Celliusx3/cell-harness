"""The composition root, and nothing else."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import resources

from mcp.server import MCPServer
from microsandbox import Image, Sandbox

from phone.clock import SYSTEM
from phone.config import ConfigError, load
from phone.engines.microsandbox import MicrosandboxEngine
from phone.services.apps import Apps
from phone.services.elements import Elements
from phone.services.live_screen import LiveScreen
from phone.services.machine import Machine
from phone.services.screen import Screen
from phone.services.touch import Touch
from phone.tools import Phone, apps, elements, manage_apps, phone_page, screenshot, touch

logger = logging.getLogger("phone")

KERNEL_VARIABLE = "MSB_LIBKRUNFW_PATH"
MSB_VARIABLE = "MSB_PATH"


def packaged_msb() -> str:
    """The msb binary the microsandbox wheel ships, at the place its docs give."""
    return str(resources.files("microsandbox._bundled").joinpath("bin", "msb"))


PHONE_INSTRUCTIONS = (
    "You have a phone: one Android phone, shared by every bot, with apps installed from APK "
    "files and no Google Play. Read its screen as text with phone__list_elements, or see it with "
    "phone__screenshot. Install an APK from this chat's files with phone__install_app, open apps "
    "with phone__open_app or links with phone__open_url, and act with phone__tap, "
    "phone__double_tap, phone__long_press, phone__swipe, phone__type_text and phone__press_key. "
    "phone__list_apps, phone__foreground_app, phone__terminate_app, phone__uninstall_app and "
    "phone__clear_app_data manage apps. Each action returns a new screenshot."
)


def build(phone: Phone) -> MCPServer:
    @asynccontextmanager
    async def lifespan(_: MCPServer) -> AsyncIterator[None]:
        async with phone.machine.serving(), phone.live_screen.serving():
            yield

    server = MCPServer(
        name="phone", version="0.1.0", instructions=PHONE_INSTRUCTIONS, lifespan=lifespan
    )
    screenshot.register(server, phone)
    elements.register(server, phone)
    apps.register(server, phone)
    manage_apps.register(server, phone)
    touch.register(server, phone)
    phone_page.register(server, phone)
    return server


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    try:
        config = load()
    except ConfigError as err:
        logger.error("phone refusing to start: %s", err)
        raise SystemExit(2) from err

    # microsandbox loads one kernel per process, and refuses its path unless msb's is given too.
    os.environ[KERNEL_VARIABLE] = str(config.kernel)
    os.environ[MSB_VARIABLE] = packaged_msb()
    engine = MicrosandboxEngine(sandboxes=Sandbox, images=Image)
    machine = Machine(engine=engine, config=config, clock=SYSTEM)
    phone = Phone(
        machine=machine,
        screen=Screen(engine=engine, name=config.name),
        apps=Apps(engine=engine, name=config.name, files_dir=config.files_dir),
        touch=Touch(engine=engine, name=config.name, clock=SYSTEM),
        elements=Elements(engine=engine, name=config.name),
        live_screen=LiveScreen(engine=engine, name=config.name, machine=machine, clock=SYSTEM),
        clock=SYSTEM,
    )
    server = build(phone)
    server.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
