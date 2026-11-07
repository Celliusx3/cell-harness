"""A microVM runs no image command by itself, so the engine starts the image's own after boot."""

from __future__ import annotations

import pytest

from computer.engines.microsandbox import MicrosandboxEngine
from computer.models.errors import EngineError
from computer.services.machine import pc_spec
from tests.conftest import IMAGE, NAME, config
from tests.fake_microsandbox import ExecCall, FakeImages, FakeSandboxes

SPEC = pc_spec(config(), ())
COMMAND = ExecCall("/usr/bin/env", ["/usr/local/bin/pc-start"], {}, None, None)


def engine_of(images: FakeImages) -> tuple[FakeSandboxes, MicrosandboxEngine]:
    vms = FakeSandboxes()
    return vms, MicrosandboxEngine(sandboxes=vms, images=images)


async def test_a_new_pc_runs_its_images_entrypoint_and_command_in_the_background() -> None:
    images = FakeImages(entrypoint=["/usr/bin/env"], cmd=["/usr/local/bin/pc-start"])
    vms, engine = engine_of(images)

    await engine.create(SPEC)

    assert images.inspected == [IMAGE]
    assert vms.launches == [COMMAND]


async def test_a_started_pc_runs_its_images_command_again() -> None:
    images = FakeImages(entrypoint=["/usr/bin/env"], cmd=["/usr/local/bin/pc-start"])
    vms, engine = engine_of(images)
    await engine.create(SPEC)
    await engine.stop(NAME)

    await engine.start(NAME)

    assert vms.launches == [COMMAND, COMMAND]


async def test_an_image_with_no_command_is_refused() -> None:
    _, engine = engine_of(FakeImages(entrypoint=None, cmd=None))

    with pytest.raises(EngineError, match="no command"):
        await engine.create(SPEC)
