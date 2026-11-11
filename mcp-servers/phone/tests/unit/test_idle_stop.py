"""The idle stop: nobody uses the phone, it stops; the next call starts it; shutdown leaves it."""

from __future__ import annotations

import logging

import pytest

from phone.models.errors import EngineError
from phone.services.machine import Machine
from tests.fakes import IDLE_SECONDS, Dial, FakeEngine, machine_over


class RefusingStop(FakeEngine):
    async def stop(self, name: str) -> None:
        raise EngineError("microsandbox stop failed: refused")


async def use(machine: Machine) -> None:
    async with machine.in_use():
        pass


async def test_after_an_idle_stop_the_next_call_starts_the_phone_and_waits_for_android() -> None:
    engine, dial = FakeEngine(state="running", boot_polls_needed=1), Dial()
    machine = machine_over(engine, dial.clock)
    async with machine.serving():
        await use(machine)
        await dial.turn(IDLE_SECONDS)
        assert (engine.stopped, engine.phone_state) == (1, "stopped")

        await use(machine)

    assert (engine.started, engine.boot_polls) == (1, 2)


async def test_a_failed_idle_stop_is_logged_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    engine, dial = RefusingStop(state="running", boot_polls_needed=1), Dial()
    machine = machine_over(engine, dial.clock)
    with caplog.at_level(logging.WARNING, logger="phone"):
        async with machine.serving():
            await use(machine)
            await dial.turn(IDLE_SECONDS)

    assert "idle stop of the phone cell-harness-phone did not happen: microsandbox stop" in (
        caplog.text
    )


async def test_shutdown_stops_nothing_and_the_idle_stop_dies_with_the_server() -> None:
    engine, dial = FakeEngine(state="running", boot_polls_needed=1), Dial()
    machine = machine_over(engine, dial.clock)
    async with machine.serving():
        await use(machine)

    await dial.turn(IDLE_SECONDS * 2)

    assert (engine.stopped, engine.phone_state) == (0, "running")
