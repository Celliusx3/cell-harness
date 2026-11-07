"""The docker engine reads docker's answers about the PC, and refuses what it cannot read."""

from __future__ import annotations

import json

import pytest

from computer.engines.docker import DockerEngine, environment_of, loopback_port
from computer.models.errors import EngineError, EngineTimeout
from tests.conftest import API_HOST_PORT, NAME, FakeDocker


def test_the_host_port_is_the_one_published_on_loopback() -> None:
    assert loopback_port(f"127.0.0.1:{API_HOST_PORT}\n", 7070) == API_HOST_PORT


@pytest.mark.parametrize("published", ["", "0.0.0.0:62477\n[::]:62477\n", "127.0.0.1:\n"])
def test_a_port_not_published_on_loopback_is_refused(published: str) -> None:
    with pytest.raises(EngineError, match="port 6080 is not published on 127.0.0.1"):
        loopback_port(published, 6080)


def test_the_environment_is_read_as_docker_prints_it() -> None:
    env = ["DISPLAY=:1", "HOME=/home/pc", "EMPTY=", "SUM=a=b"]

    assert environment_of(json.dumps(env) + "\n") == {
        "DISPLAY": ":1",
        "HOME": "/home/pc",
        "EMPTY": "",
        "SUM": "a=b",
    }


@pytest.mark.parametrize(
    ("inspected", "said"),
    [("null", "cannot read"), ("<no value>", "cannot read"), ('["DISPLAY"]', "without values")],
)
def test_an_environment_docker_answers_unreadably_is_refused(inspected: str, said: str) -> None:
    with pytest.raises(EngineError, match=said):
        environment_of(inspected)


async def test_the_host_port_and_environment_are_asked_of_docker_by_name() -> None:
    docker = FakeDocker(status="running")
    engine = DockerEngine(docker=docker)

    port = await engine.host_port(NAME, 7070)
    env = await engine.environment(NAME)

    assert port == API_HOST_PORT
    assert env["HOME"] == "/home/pc"
    assert docker.calls == [
        ["port", NAME, "7070"],
        ["inspect", "--type", "container", "--format", "{{json .Config.Env}}", NAME],
    ]


def test_a_timeout_is_caught_by_every_caller_that_catches_an_engine_error() -> None:
    with pytest.raises(EngineError, match="did not answer"):
        raise EngineTimeout("docker did not answer")
