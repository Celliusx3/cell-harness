"""How long one shell call waits on its job, and how often it looks."""

from __future__ import annotations

from computer.machine import HOME
from computer.shell import POLL_SECONDS, WAIT_SECONDS, Job, Shell
from tests.conftest import NAME, TickingClock
from tests.job_docker import JobDocker

SLEEPING = Job(command="sleep 60", stdin="", cwd=HOME)


def shell(docker: JobDocker, ticking: TickingClock) -> Shell:
    return Shell(docker=docker, container=NAME, clock=ticking.clock, variables={})


async def test_a_call_on_a_slow_command_waits_fifteen_seconds_looking_every_half_second() -> None:
    docker, ticking = JobDocker(looks_to_finish=1000), TickingClock()

    answer = await shell(docker, ticking).run(SLEEPING)

    assert answer.status == "running"
    assert ticking.now == WAIT_SECONDS
    assert len(docker.look_calls()) == 1 + WAIT_SECONDS / POLL_SECONDS


async def test_a_quick_command_answers_at_the_first_look_after_it_starts() -> None:
    docker, ticking = JobDocker(), TickingClock()

    answer = await shell(docker, ticking).run(SLEEPING)

    assert answer.status == "done"
    assert ticking.now == POLL_SECONDS
    assert len(docker.look_calls()) == 2


async def test_a_call_attaching_to_a_running_job_waits_from_when_it_was_made() -> None:
    docker, ticking = JobDocker(looks_to_finish=1000), TickingClock()
    computer = shell(docker, ticking)
    first = await computer.run(SLEEPING)

    again = await computer.run(SLEEPING)

    assert again.seconds > first.seconds
    assert ticking.now == 2 * WAIT_SECONDS
    assert len(docker.runner_calls()) == 1
