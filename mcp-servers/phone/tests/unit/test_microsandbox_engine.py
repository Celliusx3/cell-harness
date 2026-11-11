"""The microsandbox engine makes the phone as one microVM and starts the image's own command."""

from __future__ import annotations

import pytest
from microsandbox import ExecFailedError, SandboxStatus

from phone.engines.microsandbox import (
    CPUS,
    MEMORY_MIB,
    SHAPE_LABEL,
    MicrosandboxEngine,
    shape_fingerprint,
    state_of,
)
from phone.models.command import CommandResult
from phone.models.errors import EngineError, EngineTimeout
from phone.models.phone import LABEL, Program
from phone.services.machine import phone_spec
from tests.fake_microsandbox import ExecCall, FakeExecOutput, FakeImages, FakeSandboxes
from tests.fakes import CONFIG, IMAGE, NAME

SPEC = phone_spec(CONFIG)
PROGRAM = Program(argv=("android", "getprop sys.boot_completed"), env={"LANG": "C"})
IMAGE_COMMAND = ExecCall("/usr/bin/env", ["/usr/local/bin/phone-start"], {}, None, None)


def engine_of(images: FakeImages | None = None) -> tuple[FakeSandboxes, MicrosandboxEngine]:
    vms = FakeSandboxes()
    images = images or FakeImages(entrypoint=["/usr/bin/env"])
    return vms, MicrosandboxEngine(sandboxes=vms, images=images)


async def made() -> tuple[FakeSandboxes, MicrosandboxEngine]:
    vms, engine = engine_of()
    await engine.create(SPEC)
    return vms, engine


async def test_the_phone_is_made_as_a_detached_labelled_vm_of_the_spec() -> None:
    vms, _ = await made()

    [call] = vms.created
    assert (call.name, call.image, call.memory, call.cpus, call.detached) == (
        NAME,
        IMAGE,
        MEMORY_MIB,
        CPUS,
        True,
    )
    assert call.labels == {LABEL: NAME, SHAPE_LABEL: shape_fingerprint(SPEC)}


async def test_a_new_phone_runs_its_images_entrypoint_and_command_in_the_background() -> None:
    images = FakeImages(entrypoint=["/usr/bin/env"])
    vms, engine = engine_of(images)

    await engine.create(SPEC)

    assert images.inspected == [IMAGE]
    assert vms.launches == [IMAGE_COMMAND]


async def test_a_started_phone_runs_its_images_command_again() -> None:
    vms, engine = await made()
    vms.stored[NAME].status = SandboxStatus.STOPPED

    await engine.start(NAME)

    assert await engine.state(NAME) == "running"
    assert vms.calls == ["create", "start detached=True"]
    assert vms.launches == [IMAGE_COMMAND, IMAGE_COMMAND]


async def test_stopping_goes_by_name_and_leaves_a_stopped_phone() -> None:
    vms, engine = await made()

    await engine.stop(NAME)

    assert await engine.state(NAME) == "stopped"
    assert vms.calls == ["create", "stop"]


async def test_an_image_with_no_command_is_refused() -> None:
    _, engine = engine_of(FakeImages(entrypoint=None, cmd=None))

    with pytest.raises(EngineError, match="no command"):
        await engine.create(SPEC)


async def test_a_config_the_engine_cannot_read_is_refused() -> None:
    vms, engine = engine_of()
    vms.raw_config = '{"image": "nope"}'

    with pytest.raises(EngineError, match="cannot read"):
        await engine.create(SPEC)


@pytest.mark.parametrize(
    ("status", "state"),
    [
        (SandboxStatus.RUNNING, "running"),
        (SandboxStatus.STOPPED, "stopped"),
        (SandboxStatus.CRASHED, "stopped"),
        (SandboxStatus.CREATED, "stopped"),
    ],
)
def test_only_a_running_vm_is_a_running_phone(status: SandboxStatus, state: str) -> None:
    assert state_of(status) == state


async def test_a_vm_that_was_never_made_is_missing() -> None:
    _, engine = engine_of()

    assert await engine.state(NAME) == "missing"


async def test_starting_a_vm_that_was_never_made_is_an_engine_error_in_its_words() -> None:
    _, engine = engine_of()

    with pytest.raises(EngineError, match="microsandbox start failed: sandbox not found"):
        await engine.start(NAME)


async def test_a_program_runs_with_its_words_variables_stdin_and_timeout() -> None:
    vms, engine = await made()
    vms.exec_output = FakeExecOutput(3, "out\n", "err\n")

    result = await engine.run(NAME, PROGRAM, stdin="apk", timeout_seconds=12)

    assert result == CommandResult(3, "out\n", "err\n")
    [call] = vms.execs
    assert (call.cmd, call.args, call.env, call.timeout, call.stdin) == (
        "android",
        ["getprop sys.boot_completed"],
        {"LANG": "C"},
        12,
        b"apk",
    )


async def test_a_program_without_stdin_gets_none() -> None:
    vms, engine = await made()

    await engine.run(NAME, PROGRAM, stdin=None, timeout_seconds=12)

    assert vms.execs[0].stdin is None


async def test_a_program_microsandbox_times_out_is_an_engine_timeout() -> None:
    vms, engine = await made()
    vms.exec_times_out = True

    with pytest.raises(EngineTimeout, match="did not finish within 5 seconds"):
        await engine.run(NAME, PROGRAM, stdin=None, timeout_seconds=5)


async def test_a_program_that_never_answers_is_an_engine_timeout() -> None:
    vms, engine = await made()
    vms.exec_hangs = True

    with pytest.raises(EngineTimeout, match="did not finish within 0.05 seconds"):
        await engine.run(NAME, PROGRAM, stdin=None, timeout_seconds=0.05)


async def test_a_program_microsandbox_cannot_start_is_an_engine_error_in_its_words() -> None:
    vms, engine = await made()
    vms.exec_refusal = ExecFailedError("command did not start")

    with pytest.raises(EngineError, match="microsandbox exec failed: command did not start"):
        await engine.run(NAME, PROGRAM, stdin=None, timeout_seconds=5)
