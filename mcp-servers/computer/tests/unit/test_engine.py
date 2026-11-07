"""The docker engine reads docker's answers about the PC, and refuses what it cannot read."""

from __future__ import annotations

import pytest

from computer.engines.docker import DockerEngine, loopback_port
from computer.models.errors import EngineError, EngineTimeout
from tests.conftest import API_HOST_PORT, NAME, FakeDocker


def test_the_host_port_is_the_one_published_on_loopback() -> None:
    assert loopback_port(f"127.0.0.1:{API_HOST_PORT}\n", 7070) == API_HOST_PORT


@pytest.mark.parametrize("published", ["", "0.0.0.0:62477\n[::]:62477\n", "127.0.0.1:\n"])
def test_a_port_not_published_on_loopback_is_refused(published: str) -> None:
    with pytest.raises(EngineError, match="port 6080 is not published on 127.0.0.1"):
        loopback_port(published, 6080)


async def test_the_host_port_is_asked_of_docker_by_name() -> None:
    docker = FakeDocker(status="running")
    engine = DockerEngine(docker=docker)

    port = await engine.host_port(NAME, 7070)

    assert port == API_HOST_PORT
    assert docker.calls == [["port", NAME, "7070"]]


def test_a_timeout_is_caught_by_every_caller_that_catches_an_engine_error() -> None:
    with pytest.raises(EngineError, match="did not answer"):
        raise EngineTimeout("docker did not answer")
