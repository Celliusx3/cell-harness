"""The idle stop leaves the computer on while a bot's command still runs in it."""

from __future__ import annotations

import logging

import pytest

from computer.jobs import RUNNING_JOBS_SCRIPT
from computer.machine import HOME, JOBS_ROOT, Machine
from tests.conftest import IDLE_SECONDS, NAME, Dial, config
from tests.job_docker import FakeJob, JobDocker

STOP = ["stop", NAME]
RUNNING_JOBS = ["exec", NAME, "python3", "-c", RUNNING_JOBS_SCRIPT, JOBS_ROOT]
RUNNING = FakeJob(command="sleep 3600", stdin="", cwd=HOME)
WRITTEN_NOT_LAUNCHED = FakeJob(command="sleep 3600", stdin="")


def machine(docker: JobDocker, dial: Dial) -> Machine:
    return Machine(docker=docker, config=config(), clock=dial.clock)


async def test_the_idle_stop_waits_while_a_command_runs_and_stops_after_it_ends() -> None:
    docker, dial = JobDocker(), Dial()
    docker.jobs[f"{JOBS_ROOT}/0123456789abcdef"] = RUNNING
    async with machine(docker, dial).serving():
        await dial.turn(IDLE_SECONDS)
        await dial.turn(IDLE_SECONDS)
        assert STOP not in docker.calls
        assert docker.calls.count(RUNNING_JOBS) == 2

        docker.jobs.clear()
        await dial.turn(IDLE_SECONDS)

    assert docker.calls[-2:] == [RUNNING_JOBS, STOP]


async def test_a_job_folder_whose_runner_is_gone_does_not_keep_the_computer_on() -> None:
    docker, dial = JobDocker(), Dial()
    docker.jobs[f"{JOBS_ROOT}/0123456789abcdef"] = WRITTEN_NOT_LAUNCHED
    async with machine(docker, dial).serving():
        await dial.turn(IDLE_SECONDS)

    assert docker.calls[-2:] == [RUNNING_JOBS, STOP]


async def test_when_it_cannot_tell_whether_a_command_runs_the_computer_stays_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    docker, dial = JobDocker(), Dial()
    docker.refused_verbs.add("exec")
    with caplog.at_level(logging.WARNING, logger="computer"):
        async with machine(docker, dial).serving():
            await dial.turn(IDLE_SECONDS)

    assert STOP not in docker.calls
    assert "stays on: looking for running commands failed" in caplog.text


async def test_a_paused_idle_stop_is_not_armed_again_by_a_running_command() -> None:
    docker, dial = JobDocker(), Dial()
    docker.jobs[f"{JOBS_ROOT}/0123456789abcdef"] = RUNNING
    computer = machine(docker, dial)
    async with computer.serving():
        await dial.turn(IDLE_SECONDS)
        computer.pause_idle_stop()
        await dial.turn(IDLE_SECONDS * 3)

    assert docker.calls.count(RUNNING_JOBS) == 1
