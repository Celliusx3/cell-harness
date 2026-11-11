"""The live screen: a hold lasts fifteen minutes, pauses the idle stop, and is handed back."""

from __future__ import annotations

import logging
from datetime import UTC

import pytest
from mcp import Client

from phone.clock import SYSTEM
from phone.models.command import CommandResult
from phone.models.errors import EngineError
from phone.models.phone import Program
from phone.services.live_screen import HOLD_DURATION, LiveScreen, screen_url
from phone.services.machine import Machine
from tests.fakes import (
    EPOCH,
    GATEWAY_HOST_PORT,
    IDLE_SECONDS,
    NAME,
    Dial,
    FakeEngine,
    machine_over,
    phone_server,
)

HOLD_SECONDS = HOLD_DURATION.total_seconds()


class RefusingScreen(FakeEngine):
    """A phone whose `phone-screen` program fails while `refusing`."""

    refusing = True

    async def run(
        self, name: str, program: Program, *, stdin: str | None, timeout_seconds: float
    ) -> CommandResult:
        if self.refusing and program.argv[0] == "phone-screen":
            return CommandResult(1, "", "no relay")
        return await super().run(name, program, stdin=stdin, timeout_seconds=timeout_seconds)


def screen_over(engine: FakeEngine, dial: Dial) -> tuple[Machine, LiveScreen]:
    machine = machine_over(engine, dial.clock)
    return machine, LiveScreen(engine=engine, name=NAME, machine=machine, clock=dial.clock)


async def use(machine: Machine) -> None:
    async with machine.in_use():
        pass


def test_the_link_opens_novnc_on_the_published_gateway_port() -> None:
    assert screen_url(GATEWAY_HOST_PORT, "abc", view_only=True) == (
        f"http://127.0.0.1:{GATEWAY_HOST_PORT}/embed.html?path=websockify%3Ftoken%3Dabc&view_only=1"
    )


def test_the_system_wall_clock_is_utc() -> None:
    assert SYSTEM.wall().tzinfo == UTC


async def test_a_hold_lasts_fifteen_minutes_then_hands_the_phone_back() -> None:
    engine, dial = FakeEngine(state="running"), Dial()
    machine, live = screen_over(engine, dial)
    async with machine.serving(), live.serving():
        link = await live.take_control()
        assert link.session.held_until == EPOCH + HOLD_DURATION

        await dial.turn(HOLD_SECONDS - 1)
        assert live.is_held
        await dial.turn(1)

        assert not live.is_held
    assert engine.screen_commands[-1] == "phone-screen release"


async def test_the_idle_stop_waits_while_held_and_resumes_on_release() -> None:
    engine, dial = FakeEngine(state="running", boot_polls_needed=1), Dial()
    machine, live = screen_over(engine, dial)
    async with machine.serving(), live.serving():
        await use(machine)
        await live.take_control()
        await dial.turn(IDLE_SECONDS)
        assert engine.stopped == 0

        assert (await live.release()).mode == "view"
        await dial.turn(IDLE_SECONDS)

    assert engine.stopped == 1


async def test_taking_control_again_keeps_the_token_and_the_view_token_is_its_own() -> None:
    engine, dial = FakeEngine(state="running"), Dial()
    machine, live = screen_over(engine, dial)
    async with machine.serving(), live.serving():
        first = await live.take_control()
        again = await live.take_control()
        await live.release()
        viewed = await live.view()

    assert first.url == again.url
    assert viewed.url != first.url
    assert "view_only=1" in viewed.url


async def test_releasing_when_nobody_holds_the_phone_runs_nothing() -> None:
    engine, dial = FakeEngine(state="running"), Dial()
    _, live = screen_over(engine, dial)

    assert (await live.release()).held_until is None
    assert engine.screen_commands == []


async def test_a_relay_that_does_not_start_is_an_engine_error_in_its_words() -> None:
    engine, dial = RefusingScreen(state="running"), Dial()
    _, live = screen_over(engine, dial)

    with pytest.raises(EngineError, match="opening the screen failed: no relay"):
        await live.view()


async def test_an_expiry_that_cannot_close_the_control_screen_is_logged_and_ends_the_hold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine, dial = RefusingScreen(state="running"), Dial()
    engine.refusing = False
    machine, live = screen_over(engine, dial)
    async with machine.serving(), live.serving():
        await live.take_control()
        engine.refusing = True
        with caplog.at_level(logging.ERROR, logger="phone"):
            await dial.turn(HOLD_SECONDS)

        assert not live.is_held
    assert "the control screen of cell-harness-phone may still be open" in caplog.text


async def test_keep_awake_restarts_the_idle_stop() -> None:
    engine, dial = FakeEngine(state="running", boot_polls_needed=1), Dial()

    async with Client(phone_server(engine, clock=dial.clock)) as client:
        assert not (await client.call_tool("keep_awake", {})).is_error
        await dial.turn(IDLE_SECONDS - 1)
        await client.call_tool("keep_awake", {})
        await dial.turn(IDLE_SECONDS - 1)
        assert engine.stopped == 0
        await dial.turn(1)

    assert engine.stopped == 1


async def test_releasing_through_the_tool_when_not_held_says_view() -> None:
    async with Client(phone_server(FakeEngine(state="running"))) as client:
        result = await client.call_tool("release_control", {})

    assert result.structured_content == {"mode": "view", "held_until": None}
