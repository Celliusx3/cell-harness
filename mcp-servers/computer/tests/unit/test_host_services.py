"""A declared program on the Mac: started with its port, token and files, and gone afterwards."""

from __future__ import annotations

import asyncio
import logging
import re
import socket
import tempfile
from collections.abc import Sequence
from pathlib import Path

import pytest
from mcp import Client

from computer.clock import SYSTEM, Clock
from computer.docker import CommandResult
from computer.host_services import (
    LOOPBACK,
    STARTUP_SECONDS,
    PreparedHostService,
    command_variables,
    prepared_host_service,
    serving_host_services_that_start,
)
from tests.conftest import Dial, FakeDocker, server_with
from tests.fake_host_service import (
    EXIT_CODE,
    declared,
    fake_host_service,
    is_gone,
    started,
    until_started,
)


class Boom(RuntimeError):
    """What starts after the program failing."""


class BrokenDocker(FakeDocker):
    """docker failing in a way the machine does not expect, at the first call of the lifespan."""

    async def run(
        self, args: Sequence[str], *, stdin: str, timeout_seconds: float
    ) -> CommandResult:
        raise Boom("docker broke")


@pytest.fixture
def temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The system's temporary folder, here."""
    folder = tmp_path / "temp"
    folder.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(folder))
    return folder


@pytest.fixture
def files(tmp_path: Path) -> Path:
    folder = tmp_path / "files"
    folder.mkdir()
    return folder


def prepared(program: Path, files: Path, env_prefix: str = "FAKE") -> PreparedHostService:
    return prepared_host_service(declared(program, env_prefix), files)


async def body_runs(services: Sequence[PreparedHostService], clock: Clock) -> bool:
    async with serving_host_services_that_start(services, clock):
        return True


async def test_its_port_token_file_and_files_fill_the_placeholders_in_its_words(
    tmp_path: Path, files: Path, temp: Path
) -> None:
    service = prepared(fake_host_service(tmp_path, "listens"), files)

    async with serving_host_services_that_start([service], SYSTEM):
        seen = started(service.service.program)

    assert seen.args == (
        "--port", str(service.port),
        "--token-file", str(seen.token_file),
        f"--files={files}",
    )  # fmt: skip
    assert re.fullmatch(r"[0-9a-f]{64}", seen.token)
    assert seen.token == service.token


async def test_the_token_file_is_the_owners_alone_in_a_folder_outside_the_files(
    tmp_path: Path, files: Path, temp: Path
) -> None:
    service = prepared(fake_host_service(tmp_path, "listens"), files)

    async with serving_host_services_that_start([service], SYSTEM):
        seen = started(service.service.program)

    assert (seen.token_mode, seen.folder_mode) == (0o600, 0o700)
    assert seen.token_file.parent.parent == temp
    assert not seen.token_file.is_relative_to(files)


async def test_it_listens_for_the_body_then_is_killed_waited_on_and_its_token_removed(
    tmp_path: Path, files: Path, temp: Path
) -> None:
    service = prepared(fake_host_service(tmp_path, "listens"), files)

    async with serving_host_services_that_start([service], SYSTEM):
        seen = started(service.service.program)
        socket.create_connection((LOOPBACK, service.port), timeout=5).close()
        assert not is_gone(seen.pid)

    assert is_gone(seen.pid)
    assert list(temp.iterdir()) == []


async def test_every_declared_program_is_started_and_every_one_is_gone_after(
    tmp_path: Path, files: Path, temp: Path
) -> None:
    services = [
        prepared(fake_host_service(tmp_path / prefix, "listens"), files, prefix)
        for prefix in ("ONE", "TWO")
    ]

    async with serving_host_services_that_start(services, SYSTEM):
        seen = [started(service.service.program) for service in services]
        for service in services:
            socket.create_connection((LOOPBACK, service.port), timeout=5).close()

    assert all(is_gone(each.pid) for each in seen)
    assert list(temp.iterdir()) == []


async def test_it_is_gone_when_what_starts_after_it_raises(
    tmp_path: Path, files: Path, temp: Path
) -> None:
    service = prepared(fake_host_service(tmp_path, "listens"), files)

    with pytest.raises(Boom):
        async with serving_host_services_that_start([service], SYSTEM):
            raise Boom("the machine did not start")

    assert is_gone(started(service.service.program).pid)
    assert list(temp.iterdir()) == []


async def test_it_is_gone_when_the_server_lifespan_fails_after_it_started(
    tmp_path: Path, files: Path, temp: Path
) -> None:
    service = prepared(fake_host_service(tmp_path, "listens"), files)

    with pytest.raises(Boom):
        async with Client(server_with(BrokenDocker(status="running"), host_services=[service])):
            pass

    assert is_gone(started(service.service.program).pid)
    assert list(temp.iterdir()) == []


async def test_one_that_never_listens_is_killed_and_skipped_with_a_warning_and_the_body_runs(
    tmp_path: Path, files: Path, temp: Path, caplog: pytest.LogCaptureFixture
) -> None:
    service, dial = prepared(fake_host_service(tmp_path, "hangs"), files), Dial()
    entering = asyncio.create_task(body_runs([service], dial.clock))
    seen = await until_started(service.service.program)

    with caplog.at_level(logging.WARNING, logger="computer"):
        await dial.turn(STARTUP_SECONDS)
        assert await entering

    door = f"{LOOPBACK}:{service.port}"
    assert f"did not listen on {door} within 20 seconds" in caplog.text
    assert "the skill fake's program did not start" in caplog.text
    assert is_gone(seen.pid)
    assert list(temp.iterdir()) == []


async def test_one_that_exits_before_listening_is_skipped_with_its_exit_code_and_the_body_runs(
    tmp_path: Path, files: Path, temp: Path, caplog: pytest.LogCaptureFixture
) -> None:
    service = prepared(fake_host_service(tmp_path, "exits"), files)

    with caplog.at_level(logging.WARNING, logger="computer"):
        assert await body_runs([service], SYSTEM)

    assert f"exited with code {EXIT_CODE} before it listened" in caplog.text
    assert "so commands in the computer run without it" in caplog.text
    assert is_gone(started(service.service.program).pid)
    assert list(temp.iterdir()) == []


async def test_one_that_cannot_be_run_is_skipped_leaving_no_token_and_the_others_start(
    tmp_path: Path, files: Path, temp: Path, caplog: pytest.LogCaptureFixture
) -> None:
    not_a_program = tmp_path / "not-a-program"
    not_a_program.write_text("")
    working = prepared(fake_host_service(tmp_path / "working", "listens"), files, "WORKING")

    with caplog.at_level(logging.WARNING, logger="computer"):
        async with serving_host_services_that_start(
            [prepared(not_a_program, files), working], SYSTEM
        ):
            socket.create_connection((LOOPBACK, working.port), timeout=5).close()

    assert f"{not_a_program} could not be started" in caplog.text
    assert list(temp.iterdir()) == []


def test_each_service_gets_a_free_loopback_port_and_its_own_token(tmp_path: Path) -> None:
    first, second = (prepared(tmp_path / "program", tmp_path) for _ in range(2))

    assert first.token != second.token
    assert all(re.fullmatch(r"[0-9a-f]{64}", each.token) for each in (first, second))
    with socket.socket() as taken:
        taken.bind((LOOPBACK, first.port))


def test_a_command_is_handed_each_services_address_and_token_under_its_prefix(
    tmp_path: Path,
) -> None:
    one, two = (prepared(tmp_path / "program", tmp_path, prefix) for prefix in ("ONE", "TWO"))

    assert command_variables([one, two]) == {
        "ONE_ADDR": f"host.docker.internal:{one.port}",
        "ONE_TOKEN": one.token,
        "TWO_ADDR": f"host.docker.internal:{two.port}",
        "TWO_TOKEN": two.token,
    }
    assert command_variables([]) == {}
