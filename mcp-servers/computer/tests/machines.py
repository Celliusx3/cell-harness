"""A machine over the fake docker, for the tests that run no host services."""

from __future__ import annotations

from computer.clock import Clock
from computer.docker import Docker
from computer.engine import DockerEngine
from computer.machine import Machine
from tests.conftest import config

NO_HOST_SERVICES: tuple[int, ...] = ()


def docker_machine(docker: Docker, clock: Clock) -> Machine:
    return Machine(
        engine=DockerEngine(docker=docker),
        config=config(),
        clock=clock,
        host_service_ports=NO_HOST_SERVICES,
    )
