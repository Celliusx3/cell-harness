"""The one phone: made or started once, waited on until Android boots, then left alone."""

from __future__ import annotations

import pytest

from phone.models.errors import EngineError
from phone.services.machine import (
    BOOT_POLL_SECONDS,
    BOOT_TIMEOUT_SECONDS,
    GATEWAY_PORT,
    Machine,
)
from tests.fakes import BOOT_POLLS, IMAGE, NAME, FakeEngine, machine_over


async def use(machine: Machine) -> None:
    async with machine.in_use():
        pass


async def test_a_missing_phone_is_made_from_the_configs_image_and_name() -> None:
    engine = FakeEngine(state="missing")

    await use(machine_over(engine))

    [spec] = engine.specs
    assert (spec.name, spec.image) == (NAME, IMAGE)
    assert (engine.created, engine.started, engine.boot_polls) == (1, 0, BOOT_POLLS)


async def test_a_stopped_phone_is_started_and_waited_on() -> None:
    engine = FakeEngine(state="stopped")

    await use(machine_over(engine))

    assert (engine.created, engine.started, engine.boot_polls) == (0, 1, BOOT_POLLS)


async def test_a_booted_phone_is_not_polled_again() -> None:
    engine = FakeEngine(state="missing")
    machine = machine_over(engine)

    await use(machine)
    await use(machine)

    assert engine.boot_polls == BOOT_POLLS


async def test_a_phone_started_again_is_waited_on_again() -> None:
    engine = FakeEngine(state="missing", boot_polls_needed=1)
    machine = machine_over(engine)
    await use(machine)
    engine.phone_state = "stopped"

    await use(machine)

    assert (engine.started, engine.boot_polls) == (1, 2)


async def test_a_running_phone_found_at_first_use_is_polled_once_and_not_made() -> None:
    engine = FakeEngine(state="running", boot_polls_needed=1)

    await use(machine_over(engine))

    assert (engine.created, engine.started, engine.boot_polls) == (0, 0, 1)


async def test_android_that_never_boots_is_given_up_on_after_the_timeout() -> None:
    engine = FakeEngine(state="missing", boot_polls_needed=10_000)

    with pytest.raises(EngineError, match="Android did not finish booting within 180 seconds"):
        await use(machine_over(engine))

    assert engine.boot_polls == BOOT_TIMEOUT_SECONDS // BOOT_POLL_SECONDS + 1


async def test_a_phone_made_to_another_shape_is_removed_and_made_again_once() -> None:
    engine = FakeEngine(state="stopped", replacement="its published ports are not the spec's")
    machine = machine_over(engine)

    await use(machine)
    await use(machine)

    assert (engine.removed, engine.created, engine.started) == (1, 1, 0)


async def test_a_phone_of_the_specs_shape_is_kept() -> None:
    engine = FakeEngine(state="stopped")

    await use(machine_over(engine))

    assert (engine.removed, engine.created, engine.started) == (0, 0, 1)


async def test_the_spec_publishes_the_screens_gateway() -> None:
    engine = FakeEngine(state="missing")

    await use(machine_over(engine))

    assert engine.specs[0].published_ports == (GATEWAY_PORT,)
