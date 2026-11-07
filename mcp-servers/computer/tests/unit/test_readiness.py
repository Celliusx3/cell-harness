"""Whether this machine can run the PC, decided from the platform's facts."""

from __future__ import annotations

import pytest

from computer.command import CommandResult
from computer.readiness import (
    MicrosandboxHost,
    docker_problem,
    microsandbox_problem,
    refusal,
)

VIRTUALIZATION = (
    "Turn on virtualization (Apple Silicon Mac, KVM on Linux, or the Windows Hypervisor Platform)"
)


def host(
    system: str, machine: str, *, has_hypervisor: bool = True, has_runtime: bool = True
) -> MicrosandboxHost:
    return MicrosandboxHost(
        system=system, machine=machine, has_hypervisor=has_hypervisor, has_runtime=has_runtime
    )


@pytest.mark.parametrize(
    "supported",
    [
        host("Darwin", "arm64"),
        host("Linux", "x86_64"),
        host("Linux", "aarch64"),
        host("Windows", "AMD64"),
    ],
)
def test_a_machine_that_can_run_a_vm_has_no_problem(supported: MicrosandboxHost) -> None:
    assert microsandbox_problem(supported) is None


@pytest.mark.parametrize(
    ("unsupported", "said"),
    [
        (host("Darwin", "x86_64"), "this Mac is not Apple Silicon"),
        (host("Darwin", "arm64", has_hypervisor=False), "macOS reports no hypervisor"),
        (host("Linux", "x86_64", has_hypervisor=False), "/dev/kvm"),
        (host("Windows", "AMD64", has_hypervisor=False), "Windows Hypervisor Platform is off"),
        (host("FreeBSD", "amd64"), "FreeBSD is not a system the PC runs on"),
    ],
)
def test_a_machine_that_cannot_run_a_vm_says_why(unsupported: MicrosandboxHost, said: str) -> None:
    problem = microsandbox_problem(unsupported)

    assert problem is not None
    assert said in problem


def test_a_missing_runtime_is_a_problem_even_on_a_good_machine() -> None:
    problem = microsandbox_problem(host("Darwin", "arm64", has_runtime=False))

    assert problem is not None
    assert "microsandbox runtime" in problem


def test_docker_that_answers_has_no_problem() -> None:
    assert docker_problem(CommandResult(0, "Server: Docker Engine", "")) is None


def test_docker_that_refuses_says_so_in_its_own_words() -> None:
    problem = docker_problem(CommandResult(1, "", "Cannot connect to the Docker daemon\n"))

    assert problem == "docker version failed: Cannot connect to the Docker daemon"


def test_docker_that_exits_silently_names_the_exit_code() -> None:
    assert docker_problem(CommandResult(3, "", "")) == "docker version failed: exit 3"


def test_the_microsandbox_refusal_says_to_turn_on_virtualization() -> None:
    said = refusal("microsandbox", "/dev/kvm is missing")

    assert said.startswith("the PC cannot start on this computer: /dev/kvm is missing.")
    assert said.endswith(VIRTUALIZATION)


def test_the_docker_refusal_says_to_turn_on_docker() -> None:
    assert refusal("docker", "docker version failed: exit 1").endswith("Turn on Docker")
