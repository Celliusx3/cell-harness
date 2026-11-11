"""The composition root, and nothing else."""

from __future__ import annotations

import logging
import os
import sys
from importlib import resources

from mcp.server import MCPServer
from microsandbox import Image, Sandbox

from phone.clock import SYSTEM
from phone.config import ConfigError, load
from phone.engines.microsandbox import MicrosandboxEngine
from phone.services.machine import Machine
from phone.services.screen import Screen
from phone.tools import Phone, screenshot

logger = logging.getLogger("phone")

KERNEL_VARIABLE = "MSB_LIBKRUNFW_PATH"
MSB_VARIABLE = "MSB_PATH"


def packaged_msb() -> str:
    """The msb binary the microsandbox wheel ships, at the place its docs give."""
    return str(resources.files("microsandbox._bundled").joinpath("bin", "msb"))


PHONE_INSTRUCTIONS = (
    "You have a phone: one Android phone, shared by every bot, with apps installed from APK "
    "files and no Google Play. See its screen with phone__screenshot."
)


def build(phone: Phone) -> MCPServer:
    server = MCPServer(name="phone", version="0.1.0", instructions=PHONE_INSTRUCTIONS)
    screenshot.register(server, phone)
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
    server = build(Phone(machine=machine, screen=Screen(engine=engine, name=config.name)))
    server.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
