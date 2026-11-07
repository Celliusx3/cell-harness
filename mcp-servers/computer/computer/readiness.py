"""Whether this machine can run the PC, from facts about it, and what to turn on when it cannot."""

from __future__ import annotations

from dataclasses import dataclass

from computer.command import CommandResult
from computer.config import EngineName

WHAT_TO_TURN_ON: dict[EngineName, str] = {
    "microsandbox": (
        "virtualization (Apple Silicon Mac, KVM on Linux, or the Windows Hypervisor Platform)"
    ),
    "docker": "Docker",
}


@dataclass(frozen=True)
class MicrosandboxHost:
    """What the platform says about running a microsandbox VM here."""

    system: str
    machine: str
    has_hypervisor: bool
    has_runtime: bool


def microsandbox_problem(host: MicrosandboxHost) -> str | None:
    """Why a microsandbox VM cannot start on `host`, or None when it can."""
    if not host.has_runtime:
        return "the microsandbox runtime (msb and libkrunfw) is not installed"
    if host.system == "Darwin" and host.machine != "arm64":
        return "this Mac is not Apple Silicon"
    if host.system not in _NO_HYPERVISOR:
        return f"{host.system} is not a system the PC runs on"
    if not host.has_hypervisor:
        return _NO_HYPERVISOR[host.system]
    return None


_NO_HYPERVISOR = {
    "Darwin": "macOS reports no hypervisor support",
    "Linux": "/dev/kvm is missing, or this user cannot read and write it",
    "Windows": "the Windows Hypervisor Platform is off",
}


def docker_problem(completed: CommandResult) -> str | None:
    """Why `docker version` says Docker cannot run the PC, or None when it answered."""
    if completed.returncode == 0:
        return None
    said = completed.stderr.strip() or f"exit {completed.returncode}"
    return f"docker version failed: {said}"


def refusal(engine: EngineName, problem: str) -> str:
    """The message the server exits with: what is wrong, and what to turn on."""
    return f"the PC cannot start on this computer: {problem}. Turn on {WHAT_TO_TURN_ON[engine]}"
