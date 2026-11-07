"""Gathers the facts `readiness` decides on: the platform, its hypervisor, and Docker."""

from __future__ import annotations

import os
import platform
import subprocess
from collections.abc import Callable
from pathlib import Path

from microsandbox import is_runtime_installed

from computer.config import EngineName
from computer.engines.docker import Docker
from computer.models.errors import EngineError
from computer.readiness import MicrosandboxHost, docker_problem, microsandbox_problem, refusal

DOCKER_CHECK_TIMEOUT_SECONDS = 15.0
SYSCTL_TIMEOUT_SECONDS = 5.0
KVM_DEVICE = Path("/dev/kvm")


def probed_host() -> MicrosandboxHost:
    """This machine, as the platform describes it, without booting anything."""
    system = platform.system()
    return MicrosandboxHost(
        system=system,
        machine=platform.machine(),
        has_hypervisor=_has_hypervisor(system),
        has_runtime=is_runtime_installed(),
    )


def _has_hypervisor(system: str) -> bool:
    if system == "Darwin":
        return _mac_has_hypervisor()
    if system == "Linux":
        return KVM_DEVICE.exists() and os.access(KVM_DEVICE, os.R_OK | os.W_OK)
    if system == "Windows":
        root = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
        return (root / "System32" / "WinHvPlatform.dll").exists()
    return False


def _mac_has_hypervisor() -> bool:
    try:
        completed = subprocess.run(
            ["sysctl", "-n", "kern.hv_support"],
            capture_output=True,
            text=True,
            timeout=SYSCTL_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.stdout.strip() == "1"


async def host_refusal(
    engine: EngineName, *, docker: Docker, host: Callable[[], MicrosandboxHost]
) -> str | None:
    """Why this machine cannot run the PC on `engine`, said as what to turn on, or None."""
    problem = microsandbox_problem(host()) if engine == "microsandbox" else await _docker(docker)
    return None if problem is None else refusal(engine, problem)


async def _docker(docker: Docker) -> str | None:
    try:
        completed = await docker.run(
            ["version"], stdin="", timeout_seconds=DOCKER_CHECK_TIMEOUT_SECONDS
        )
    except EngineError as err:
        return str(err)
    return docker_problem(completed)
