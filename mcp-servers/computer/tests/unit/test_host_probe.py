"""The probe gathers the facts; the server refuses to start when they say the PC cannot run."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import pytest

from computer import host_probe, server
from computer.models.command import CommandResult
from computer.models.errors import EngineError
from computer.readiness import MicrosandboxHost


class AnsweringDocker:
    def __init__(self, completed: CommandResult | EngineError) -> None:
        self.completed = completed
        self.calls: list[list[str]] = []

    async def run(
        self, args: Sequence[str], *, stdin: str, timeout_seconds: float
    ) -> CommandResult:
        self.calls.append(list(args))
        if isinstance(self.completed, EngineError):
            raise self.completed
        return self.completed


def no_hypervisor() -> MicrosandboxHost:
    return MicrosandboxHost(
        system="Linux", machine="x86_64", has_hypervisor=False, has_runtime=True
    )


def a_good_mac() -> MicrosandboxHost:
    return MicrosandboxHost(system="Darwin", machine="arm64", has_hypervisor=True, has_runtime=True)


async def test_docker_is_asked_for_its_version() -> None:
    docker = AnsweringDocker(CommandResult(0, "Server: Docker Engine", ""))

    assert await host_probe.host_refusal("docker", docker=docker, host=a_good_mac) is None
    assert docker.calls == [["version"]]


async def test_docker_missing_from_path_is_refused_with_what_to_turn_on() -> None:
    docker = AnsweringDocker(EngineError("docker is not on PATH: install Docker and start it"))

    said = await host_probe.host_refusal("docker", docker=docker, host=a_good_mac)

    assert said is not None
    assert "docker is not on PATH" in said
    assert said.endswith("Turn on Docker")


async def test_microsandbox_on_a_machine_without_a_hypervisor_is_refused() -> None:
    docker = AnsweringDocker(CommandResult(0, "", ""))

    said = await host_probe.host_refusal("microsandbox", docker=docker, host=no_hypervisor)

    assert said is not None
    assert "virtualization" in said
    assert docker.calls == []


def test_this_machine_is_described_by_its_own_platform() -> None:
    probed = host_probe.probed_host()

    assert probed.system
    assert probed.machine


def test_the_server_exits_non_zero_with_the_refusal_before_it_serves(
    monkeypatch, tmp_path: Path, caplog
) -> None:
    monkeypatch.setenv("COMPUTER_ENGINE", "microsandbox")
    monkeypatch.setenv("COMPUTER_FILES_DIR", str(tmp_path))
    monkeypatch.setenv("COMPUTER_SKILLS_DIRS", str(tmp_path))
    monkeypatch.setattr(host_probe, "probed_host", no_hypervisor)
    monkeypatch.setattr(server, "build", lambda *_: pytest.fail("the server was built"))

    with caplog.at_level(logging.ERROR, logger="computer"), pytest.raises(SystemExit) as exit:
        server.main()

    assert exit.value.code == 2
    assert "Turn on virtualization" in caplog.text
