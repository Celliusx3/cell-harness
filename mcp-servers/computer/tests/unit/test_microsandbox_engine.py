"""The microsandbox engine makes the PC as one microVM, and reads it back from the VM's config."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from microsandbox import ExecFailedError, MountKind, NamedVolumeMode, SandboxStatus

from computer.engines.microsandbox import (
    CPUS,
    CREATE_TIMEOUT_SECONDS,
    MEMORY_MIB,
    MicrosandboxEngine,
    state_of,
)
from computer.models.command import COMMAND_TIMEOUT_SECONDS, CommandResult
from computer.models.errors import EngineError, EngineTimeout
from computer.models.pc import HOME, PcSpec, Program, SharedFolder
from computer.services.machine import GATEWAY_PORT, SHM_MEGABYTES, pc_spec
from tests.conftest import FILES_DIR, IMAGE, NAME, SKILLS_DIR, config
from tests.fake_microsandbox import FakeExecOutput, FakeImages, FakeSandboxes

SPEC = pc_spec(config(), ())
PROGRAM = Program(argv=("python3", "-c", "print(1)"), env={"LANG": "C.UTF-8"})


async def made() -> tuple[FakeSandboxes, MicrosandboxEngine]:
    vms = FakeSandboxes()
    engine = MicrosandboxEngine(sandboxes=vms, images=FakeImages())
    await engine.create(SPEC)
    return vms, engine


def test_creating_waits_longer_than_a_command_for_the_first_image_pull() -> None:
    assert CREATE_TIMEOUT_SECONDS > COMMAND_TIMEOUT_SECONDS


async def test_the_pc_is_made_as_a_detached_vm_of_the_spec() -> None:
    vms, _ = await made()

    [call] = vms.created
    assert (call.name, call.image, call.memory, call.cpus, call.detached) == (
        NAME,
        IMAGE,
        MEMORY_MIB,
        CPUS,
        True,
    )
    assert call.env == {"DISPLAY": ":1", "HOME": HOME}


async def test_only_the_gateway_is_published_on_a_free_loopback_port() -> None:
    vms, _ = await made()

    (port,) = vms.created[0].ports
    assert (port.guest_port, port.bind) == (GATEWAY_PORT, "127.0.0.1")
    assert port.host_port > 0


async def test_the_home_is_a_named_volume_and_the_shared_folders_are_bind_mounts() -> None:
    vms, _ = await made()

    volumes = vms.created[0].volumes
    home = volumes[HOME]
    assert (home.kind, home.named, home.named_mode) == (
        MountKind.NAMED,
        f"{NAME}-home",
        NamedVolumeMode.ENSURE_EXISTS,
    )
    files, skills = volumes[str(FILES_DIR)], volumes[str(SKILLS_DIR)]
    assert (files.kind, files.bind, files.readonly) == (MountKind.BIND, str(FILES_DIR), False)
    assert (skills.kind, skills.bind, skills.readonly) == (MountKind.BIND, str(SKILLS_DIR), True)


async def test_shared_memory_is_a_tmpfs_of_the_spec_size() -> None:
    vms, _ = await made()

    shm = vms.created[0].volumes["/dev/shm"]
    assert (shm.kind, shm.size_mib) == (MountKind.TMPFS, SHM_MEGABYTES)


async def test_the_host_port_is_read_back_from_the_vm_after_this_server_restarts() -> None:
    vms, _ = await made()
    published = {port.guest_port: port.host_port for port in vms.created[0].ports}

    reloaded = MicrosandboxEngine(sandboxes=vms, images=FakeImages())

    assert await reloaded.host_port(NAME, GATEWAY_PORT) == published[GATEWAY_PORT]


async def test_a_port_not_published_on_loopback_is_refused() -> None:
    vms, engine = await made()
    stored = vms.stored[NAME].config
    vms.raw_config = json.dumps(stored).replace("127.0.0.1", "0.0.0.0")

    with pytest.raises(EngineError, match="port 6080 is not published on 127.0.0.1"):
        await engine.host_port(NAME, GATEWAY_PORT)
    with pytest.raises(EngineError, match="port 5900 is not published on 127.0.0.1"):
        await engine.host_port(NAME, 5900)


async def test_a_config_the_engine_cannot_read_is_refused() -> None:
    vms, engine = await made()
    vms.raw_config = '{"env": "nope"}'

    with pytest.raises(EngineError, match="cannot read"):
        await engine.host_port(NAME, GATEWAY_PORT)


@pytest.mark.parametrize(
    ("status", "state"),
    [
        (SandboxStatus.RUNNING, "running"),
        (SandboxStatus.STOPPED, "stopped"),
        (SandboxStatus.CRASHED, "stopped"),
        (SandboxStatus.CREATED, "stopped"),
        (SandboxStatus.PAUSED, "stopped"),
    ],
)
def test_only_a_running_vm_is_a_running_pc(status: SandboxStatus, state: str) -> None:
    assert state_of(status) == state


async def test_a_vm_that_was_never_made_is_missing() -> None:
    assert (
        await MicrosandboxEngine(sandboxes=FakeSandboxes(), images=FakeImages()).state(NAME)
        == "missing"
    )


async def test_stopping_starting_and_removing_go_by_name() -> None:
    vms, engine = await made()

    await engine.stop(NAME)
    assert await engine.state(NAME) == "stopped"
    await engine.start(NAME)
    assert await engine.state(NAME) == "running"
    await engine.remove(NAME)

    assert await engine.state(NAME) == "missing"
    assert vms.calls == ["create", "stop", "start detached=True", "stop", "remove"]


async def test_a_stopped_vm_is_removed_without_stopping_it_again() -> None:
    vms, engine = await made()
    await engine.stop(NAME)

    await engine.remove(NAME)

    assert vms.calls == ["create", "stop", "remove"]


async def test_a_refusal_from_microsandbox_is_an_engine_error_in_its_words() -> None:
    engine = MicrosandboxEngine(sandboxes=FakeSandboxes(), images=FakeImages())

    with pytest.raises(EngineError, match="microsandbox stop failed: sandbox not found"):
        await engine.stop(NAME)


async def test_a_program_runs_with_its_words_variables_stdin_and_timeout() -> None:
    vms, engine = await made()
    vms.exec_output = FakeExecOutput(3, "out\n", "err\n")

    result = await engine.run(NAME, PROGRAM, stdin="secret", timeout_seconds=12)

    assert result == CommandResult(3, "out\n", "err\n")
    [call] = vms.execs
    assert (call.cmd, call.args, call.env, call.timeout, call.stdin) == (
        "python3",
        ["-c", "print(1)"],
        {"LANG": "C.UTF-8"},
        12,
        b"secret",
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


async def test_a_launch_starts_the_program_detached() -> None:
    vms, engine = await made()

    result = await engine.launch(NAME, PROGRAM)

    assert result.returncode == 0
    [_image_command, call] = vms.launches
    assert (call.cmd, call.args, call.env) == ("python3", ["-c", "print(1)"], {"LANG": "C.UTF-8"})


async def test_the_pc_made_from_the_spec_needs_no_replacing() -> None:
    _, engine = await made()

    assert await engine.replacement_reason(SPEC) is None


@pytest.mark.parametrize(
    "changed",
    [
        dataclasses.replace(SPEC, published_ports=(GATEWAY_PORT, 5900)),
        dataclasses.replace(SPEC, shared_folders=(SharedFolder(Path("/tmp/other"), True),)),
        dataclasses.replace(SPEC, shared_folders=(SharedFolder(FILES_DIR, False),)),
    ],
)
async def test_a_pc_made_with_other_ports_or_folders_is_replaced(changed: PcSpec) -> None:
    _, engine = await made()

    assert await engine.replacement_reason(changed) == (
        "its published ports, shared folders or network rules are not the spec's"
    )


async def test_a_vm_without_the_shape_label_is_replaced() -> None:
    vms, engine = await made()
    vms.stored[NAME].config["labels"] = {}

    assert await engine.replacement_reason(SPEC) is not None


def test_the_mac_is_reached_by_the_name_microsandbox_gives_it() -> None:
    engine = MicrosandboxEngine(sandboxes=FakeSandboxes(), images=FakeImages())

    assert engine.host_address == "host.microsandbox.internal"
