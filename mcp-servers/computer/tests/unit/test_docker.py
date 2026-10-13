"""The real docker seam, run against a stand-in executable."""

from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path

import pytest

from computer.docker import CommandResult, DockerCli, DockerError, DockerTimeout, stdout_of

STAND_IN = """#!/bin/sh
case "$1" in
  echo) shift; cat; printf ' %s' "$@" ;;
  refuse) echo "Error response from daemon: No such container: x" >&2; exit 1 ;;
  hang) echo $$ > "$2"; exec sleep 30 ;;
esac
"""


@pytest.fixture
def docker(tmp_path: Path) -> DockerCli:
    script = tmp_path / "docker"
    script.write_text(STAND_IN)
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return DockerCli(executable=str(script))


async def test_arguments_go_on_argv_and_stdin_goes_on_stdin(docker: DockerCli) -> None:
    completed = await docker.run(["echo", "exec", "box"], stdin='{"url": "x"}', timeout_seconds=5)

    assert completed == CommandResult(returncode=0, stdout='{"url": "x"} exec box', stderr="")


async def test_a_refusal_is_returned_for_the_caller_to_judge(docker: DockerCli) -> None:
    completed = await docker.run(["refuse"], stdin="", timeout_seconds=5)

    assert completed.returncode == 1
    assert "No such container" in completed.stderr


async def test_a_command_that_outlives_its_timeout_is_killed(
    docker: DockerCli, tmp_path: Path
) -> None:
    pid_file = tmp_path / "pid"

    with pytest.raises(DockerTimeout, match="within 0.2 seconds"):
        await docker.run(["hang", str(pid_file)], stdin="", timeout_seconds=0.2)

    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


async def test_a_cancelled_command_leaves_no_process_behind(
    docker: DockerCli, tmp_path: Path
) -> None:
    pid_file = tmp_path / "pid"
    task = asyncio.create_task(docker.run(["hang", str(pid_file)], stdin="", timeout_seconds=30))
    while not pid_file.exists() or not pid_file.read_text().strip():
        await asyncio.sleep(0.01)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


async def test_no_docker_on_path_says_so() -> None:
    with pytest.raises(DockerError, match="not on PATH"):
        await DockerCli(executable="/nonexistent/docker").run(["ps"], stdin="", timeout_seconds=5)


def test_a_successful_command_hands_back_its_stdout() -> None:
    assert (
        stdout_of(CommandResult(returncode=0, stdout="ok\n", stderr=""), "docker start") == "ok\n"
    )


def test_a_failed_command_raises_in_dockers_own_words() -> None:
    refused = CommandResult(returncode=125, stdout="", stderr="Conflict. The name is in use.\n")

    with pytest.raises(DockerError, match="docker run failed: Conflict. The name is in use."):
        stdout_of(refused, "docker run")


def test_a_silent_failure_names_its_exit_code() -> None:
    with pytest.raises(DockerError, match="exit 3"):
        stdout_of(CommandResult(returncode=3, stdout="", stderr=""), "docker stop")
