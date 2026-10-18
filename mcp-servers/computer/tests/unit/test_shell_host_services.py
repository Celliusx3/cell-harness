"""Every command the shell runs is told where each declared program listens, and its token."""

from __future__ import annotations

from pathlib import Path

from mcp import Client

from computer.host_services import prepared_host_service
from computer.jobs import LOOK_SCRIPT, RUNNER_SCRIPT, WRITE_SCRIPT
from tests.conftest import NAME, server_with
from tests.fake_host_service import declared, fake_host_service, started
from tests.job_docker import JobDocker

SLOW = 100


def shell_calls(docker: JobDocker) -> list[list[str]]:
    scripts = (WRITE_SCRIPT, RUNNER_SCRIPT, LOOK_SCRIPT)
    return [call for call in docker.calls if any(script in call for script in scripts)]


async def test_every_exec_of_the_shell_tool_carries_each_declared_programs_address_and_token(
    tmp_path: Path,
) -> None:
    (tmp_path / "files").mkdir()
    services = [
        prepared_host_service(
            declared(fake_host_service(tmp_path / prefix, "listens"), prefix), tmp_path / "files"
        )
        for prefix in ("COMIC", "MAPS")
    ]
    docker = JobDocker(looks_to_finish=SLOW)
    async with Client(server_with(docker, host_services=services)) as client:
        seen = [started(service.service.program) for service in services]
        for _ in range(2):
            await client.call_tool("shell", {"command": "sleep 60"})

    comic_port, maps_port = (each.args[each.args.index("--port") + 1] for each in seen)
    variables = [
        "-e", f"COMIC_ADDR=host.docker.internal:{comic_port}",
        "-e", f"COMIC_TOKEN={seen[0].token}",
        "-e", f"MAPS_ADDR=host.docker.internal:{maps_port}",
        "-e", f"MAPS_TOKEN={seen[1].token}",
    ]  # fmt: skip
    calls = shell_calls(docker)
    assert {call[1] for call in calls} == {"-i", "-d"}
    assert all(call[2:11] == [*variables, NAME] for call in calls), calls


async def test_no_exec_of_the_shell_tool_carries_a_variable_when_no_skill_declares_one() -> None:
    docker = JobDocker()
    async with Client(server_with(docker)) as client:
        await client.call_tool("shell", {"command": "ls"})

    calls = shell_calls(docker)
    assert calls
    assert all(call[2] == NAME for call in calls)
    assert "-e" not in [arg for call in calls for arg in call]
