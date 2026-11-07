"""The server runs the PC on the engine COMPUTER_ENGINE names."""

from __future__ import annotations

from microsandbox import Image, Sandbox

from computer.engines.docker import DockerCli, DockerEngine
from computer.engines.microsandbox import MicrosandboxEngine
from computer.server import engine_named


def test_docker_runs_the_pc_through_the_docker_command_line() -> None:
    assert engine_named("docker") == DockerEngine(docker=DockerCli(executable="docker"))


def test_microsandbox_runs_the_pc_through_the_microsandbox_sdk() -> None:
    assert engine_named("microsandbox") == MicrosandboxEngine(sandboxes=Sandbox, images=Image)
