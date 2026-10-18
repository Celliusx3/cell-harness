"""The composition root, and nothing else."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from importlib import resources

import httpx
from mcp.server import MCPServer
from mcp.server.apps import Apps, ResourceCsp

from computer.browser import Browser
from computer.clock import SYSTEM
from computer.config import ConfigError, load
from computer.desktop import Desktop
from computer.docker import DockerCli
from computer.files import Files
from computer.host_services import (
    PreparedHostService,
    command_variables,
    prepared_host_service,
    serving_host_services_that_start,
)
from computer.live_screen import LiveScreen
from computer.machine import Machine
from computer.shell import Shell
from computer.skill_declarations import declared_host_services
from computer.tools import PREVIEW_URI, Computer, browser, computer_page, shell

logger = logging.getLogger("computer")


def build(computer: Computer, host_services: Sequence[PreparedHostService]) -> MCPServer:
    @asynccontextmanager
    async def lifespan(_: MCPServer) -> AsyncIterator[None]:
        async with (
            serving_host_services_that_start(host_services, SYSTEM),
            computer.machine.serving(),
            computer.live_screen.serving(),
        ):
            yield

    preview = Apps()
    preview_html = resources.files("computer").joinpath("preview.html").read_text(encoding="utf-8")
    preview.add_html_resource(PREVIEW_URI, preview_html, csp=ResourceCsp())
    browser.register_navigate(preview, computer)
    server = MCPServer(
        name="computer",
        version="0.1.0",
        lifespan=lifespan,
        extensions=[preview],
    )
    browser.register_read_and_act(server, computer)
    computer_page.register(server, computer)
    shell.register(server, computer)
    return server


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    try:
        config = load()
    except ConfigError as err:
        logger.error("computer refusing to start: %s", err)
        raise SystemExit(2) from err

    docker = DockerCli(executable="docker")
    machine = Machine(docker=docker, config=config, clock=SYSTEM)
    host_services = tuple(
        prepared_host_service(service, config.files_dir)
        for service in declared_host_services(config.skills_dirs, os.environ.get("PATH", ""))
    )
    server = build(
        Computer(
            machine=machine,
            browser=Browser(docker=docker, container=config.container_name, clock=SYSTEM),
            desktop=Desktop(
                docker=docker,
                container=config.container_name,
                client=httpx.AsyncClient(trust_env=False),
            ),
            live_screen=LiveScreen(
                docker=docker, container=config.container_name, machine=machine, clock=SYSTEM
            ),
            files=Files(docker=docker, container=config.container_name),
            shell=Shell(
                docker=docker,
                container=config.container_name,
                clock=SYSTEM,
                variables=command_variables(host_services),
            ),
        ),
        host_services,
    )
    server.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
