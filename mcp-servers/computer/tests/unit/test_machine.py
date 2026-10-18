"""The one computer: made once, reused, started again, adopted, and stopped when idle."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from computer.docker import DockerError
from computer.jobs import RUNNING_JOBS_SCRIPT
from computer.machine import JOBS_ROOT, Machine
from tests.conftest import IDLE_SECONDS, IMAGE, NAME, Dial, FakeDocker, config, settle

INSPECT = ["inspect", "--type", "container", "--format", "{{.State.Status}}", NAME]
BINDINGS = ["inspect", "--type", "container", "--format", "{{json .HostConfig.PortBindings}}", NAME]
MOUNTS = ["inspect", "--type", "container", "--format", "{{json .Mounts}}", NAME]
STOP = ["stop", NAME]
OPEN_CHROME_CALL = ["exec", "-d", NAME, "rakazo-focus-or-launch", "rakazo-browser"]
RUNNING_JOBS = ["exec", NAME, "python3", "-c", RUNNING_JOBS_SCRIPT, JOBS_ROOT]


@asynccontextmanager
async def serving(docker: FakeDocker, dial: Dial) -> AsyncIterator[Machine]:
    machine = Machine(docker=docker, config=config(), clock=dial.clock)
    async with machine.serving():
        docker.calls.clear()
        yield machine


async def use(machine: Machine) -> None:
    async with machine.in_use():
        pass


async def test_the_first_call_runs_one_container_with_rakazos_options() -> None:
    docker = FakeDocker(status="missing")
    async with serving(docker, Dial()) as machine:
        await use(machine)

    inspect, run, launch = docker.calls
    files, skills = config().files_dir, config().skills_dirs[0]
    token = next(arg for arg in run if arg.startswith("RAKAZO_COMPUTER_CONTROL_TOKEN="))
    assert inspect == INSPECT
    assert re.fullmatch(r"RAKAZO_COMPUTER_CONTROL_TOKEN=[0-9a-f]{32}", token)
    assert run == [
        "run", "-d", "--name", NAME,
        "--label", f"cell-harness.computer={NAME}",
        "--shm-size", "256m",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        "-e", "DISPLAY=:1",
        "-e", "HOME=/home/rakazo",
        "-e", token,
        "-v", f"{NAME}-home:/home/rakazo",
        "-v", f"{files}:{files}",
        "-v", f"{skills}:{skills}:ro",
        "-p", "127.0.0.1::7070",
        "-p", "127.0.0.1::6080",
        IMAGE,
    ]  # fmt: skip
    assert launch == OPEN_CHROME_CALL


async def test_the_second_call_reuses_the_running_container() -> None:
    docker = FakeDocker(status="missing")
    async with serving(docker, Dial()) as machine:
        await use(machine)
        await use(machine)

    assert docker.verbs() == ["inspect", "run", "exec", "inspect"]


async def test_a_stopped_container_is_started_not_run_again() -> None:
    docker = FakeDocker(status="exited")
    async with serving(docker, Dial()) as machine:
        await use(machine)

    assert docker.calls == [INSPECT, BINDINGS, MOUNTS, ["start", NAME], OPEN_CHROME_CALL]


async def test_a_container_with_the_gateway_port_is_reused_and_its_ports_read_only_once() -> None:
    docker = FakeDocker(status="running")
    async with serving(docker, Dial()) as machine:
        await use(machine)
        await use(machine)

    assert docker.calls == [INSPECT, BINDINGS, MOUNTS, INSPECT]


@pytest.mark.parametrize("status", ["running", "exited"])
async def test_a_container_made_without_the_gateway_port_is_replaced_keeping_its_home(
    status: str,
) -> None:
    docker = FakeDocker(status=status)
    docker.bindings = {"7070/tcp": [{"HostIp": "127.0.0.1", "HostPort": ""}]}
    async with serving(docker, Dial()) as machine:
        docker.calls.clear()
        await use(machine)
        await use(machine)

    inspect, bindings, remove, run, launch, again = docker.calls
    assert (inspect, bindings, remove) == (INSPECT, BINDINGS, ["rm", "-f", NAME])
    assert run[0] == "run"
    assert f"{NAME}-home:/home/rakazo" in run
    assert "127.0.0.1::6080" in run
    assert (launch, again) == (OPEN_CHROME_CALL, INSPECT)


@pytest.mark.parametrize("answer", ["not json", '{"6080/tcp": "everywhere"}'])
async def test_ports_docker_answers_unreadably_are_refused(answer: str) -> None:
    docker = FakeDocker(status="running")
    docker.raw_bindings = answer
    async with serving(docker, Dial()) as machine:
        with pytest.raises(DockerError, match="cannot read"):
            await use(machine)

    assert "rm" not in docker.verbs()


async def test_a_paused_idle_stop_waits_and_restarts_when_resumed() -> None:
    docker, dial = FakeDocker(status="missing"), Dial()
    async with serving(docker, dial) as machine:
        await use(machine)
        machine.pause_idle_stop()
        await use(machine)
        await dial.turn(IDLE_SECONDS * 3)
        assert STOP not in docker.calls

        machine.resume_idle_stop()
        await dial.turn(IDLE_SECONDS)

    assert docker.calls[-1] == STOP


async def test_two_concurrent_first_calls_run_exactly_one_container() -> None:
    docker = FakeDocker(status="missing")
    async with serving(docker, Dial()) as machine:
        await asyncio.gather(use(machine), use(machine))

    assert docker.verbs().count("run") == 1


async def test_a_refused_docker_command_raises_in_dockers_words() -> None:
    docker = FakeDocker(status="missing")
    docker.refused_verbs.add("run")
    async with serving(docker, Dial()) as machine:
        with pytest.raises(DockerError, match="docker run failed: Error: run refused"):
            await use(machine)


async def test_the_idle_stop_fires_after_idle_minutes_with_no_call() -> None:
    docker, dial = FakeDocker(status="missing"), Dial()
    async with serving(docker, dial) as machine:
        await use(machine)
        await dial.turn(IDLE_SECONDS - 1)
        assert STOP not in docker.calls

        await dial.turn(1)

    assert docker.calls[-1] == STOP
    assert docker.status == "exited"


async def test_a_call_in_between_postpones_the_idle_stop() -> None:
    docker, dial = FakeDocker(status="missing"), Dial()
    async with serving(docker, dial) as machine:
        await use(machine)
        await dial.turn(IDLE_SECONDS - 60)
        await use(machine)
        await dial.turn(IDLE_SECONDS - 60)
        assert STOP not in docker.calls

        await dial.turn(60)

    assert docker.calls[-1] == STOP


async def test_a_call_during_the_idle_stop_waits_for_it_then_starts_the_computer_again() -> None:
    docker, dial = FakeDocker(status="missing"), Dial()
    docker.gates["stop"] = asyncio.Event()
    async with serving(docker, dial) as machine:
        await use(machine)
        await dial.turn(IDLE_SECONDS)
        call = asyncio.create_task(use(machine))
        await settle()
        docker.gates["stop"].set()
        await call

    assert docker.verbs() == ["inspect", "run", "exec", "exec", "stop", "inspect", "start", "exec"]
    assert docker.status == "running"


async def test_a_failed_idle_stop_is_logged_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    docker, dial = FakeDocker(status="missing"), Dial()
    docker.refused_verbs.add("stop")
    async with serving(docker, dial) as machine:
        await use(machine)
        with caplog.at_level(logging.WARNING, logger="computer"):
            await dial.turn(IDLE_SECONDS)

    assert "docker stop failed" in caplog.text


async def test_a_running_container_is_adopted_at_startup_and_its_idle_stop_armed() -> None:
    docker, dial = FakeDocker(status="running"), Dial()
    machine = Machine(docker=docker, config=config(), clock=dial.clock)
    async with machine.serving():
        await dial.turn(IDLE_SECONDS)

    assert docker.calls == [INSPECT, OPEN_CHROME_CALL, RUNNING_JOBS, STOP]


async def test_a_stopped_or_missing_container_is_left_alone_at_startup() -> None:
    for status in ("exited", "missing"):
        docker, dial = FakeDocker(status=status), Dial()
        machine = Machine(docker=docker, config=config(), clock=dial.clock)
        async with machine.serving():
            await dial.turn(IDLE_SECONDS)

        assert docker.calls == [INSPECT]


async def test_shutdown_stops_nothing_and_the_idle_stop_dies_with_the_server() -> None:
    docker, dial = FakeDocker(status="running"), Dial()
    machine = Machine(docker=docker, config=config(), clock=dial.clock)
    async with machine.serving():
        pass
    await dial.turn(IDLE_SECONDS)

    assert docker.calls == [INSPECT, OPEN_CHROME_CALL]
    assert docker.status == "running"


async def test_docker_unreachable_at_startup_is_logged_and_the_server_still_starts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    docker = FakeDocker(status="running")
    docker.unreachable = True
    machine = Machine(docker=docker, config=config(), clock=Dial().clock)
    with caplog.at_level(logging.WARNING, logger="computer"):
        async with machine.serving():
            pass

    assert "not on PATH" in caplog.text


async def test_a_computer_started_again_opens_chrome_so_its_screen_is_not_black() -> None:
    docker = FakeDocker(status="exited")
    async with serving(docker, Dial()) as machine:
        await use(machine)

    assert docker.calls == [INSPECT, BINDINGS, MOUNTS, ["start", NAME], OPEN_CHROME_CALL]


async def test_a_new_computer_opens_chrome() -> None:
    docker = FakeDocker(status="missing")
    async with serving(docker, Dial()) as machine:
        await use(machine)

    assert docker.launches() == [OPEN_CHROME_CALL]


async def test_a_running_computer_adopted_at_startup_opens_chrome() -> None:
    docker = FakeDocker(status="running")
    machine = Machine(docker=docker, config=config(), clock=Dial().clock)
    async with machine.serving():
        pass

    assert docker.launches() == [OPEN_CHROME_CALL]


async def test_a_computer_already_running_is_not_asked_to_open_chrome_on_every_call() -> None:
    docker = FakeDocker(status="missing")
    async with serving(docker, Dial()) as machine:
        await use(machine)
        await use(machine)
        await use(machine)

    assert len(docker.launches()) == 1


async def test_chrome_failing_to_open_is_logged_and_the_call_still_runs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    docker = FakeDocker(status="exited")
    docker.refused_verbs.add("exec")
    with caplog.at_level(logging.WARNING, logger="computer"):
        async with serving(docker, Dial()) as machine:
            await use(machine)

    assert docker.status == "running"
    assert "Chrome did not open" in caplog.text
