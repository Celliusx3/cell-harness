"""The phone stops when idle, and keeps Android's data on a disk that outlives a stop."""

from __future__ import annotations

from mcp import Client
from microsandbox import NamedVolumeMode, VolumeKind

from phone.engines.microsandbox import DATA_GUEST_PATH, DATA_MIB
from tests.fakes import IDLE_SECONDS, NAME, Dial, FakeEngine, phone_server
from tests.unit.test_microsandbox_engine import made


async def test_the_phone_stops_after_its_idle_minutes_with_no_call() -> None:
    dial = Dial()
    engine = FakeEngine(state="running", boot_polls_needed=1)

    async with Client(phone_server(engine, clock=dial.clock)) as client:
        await client.call_tool("screenshot", {})
        await dial.turn(IDLE_SECONDS - 1)
        assert engine.stopped == 0
        await dial.turn(1)
        assert engine.stopped == 1


async def test_a_call_in_between_postpones_the_stop() -> None:
    dial = Dial()
    engine = FakeEngine(state="running", boot_polls_needed=1)

    async with Client(phone_server(engine, clock=dial.clock)) as client:
        await client.call_tool("screenshot", {})
        await dial.turn(IDLE_SECONDS - 60)
        await client.call_tool("screenshot", {})
        await dial.turn(120)
        assert engine.stopped == 0
        await dial.turn(IDLE_SECONDS)
        assert engine.stopped == 1


async def test_androids_data_is_on_a_named_disk_volume_that_outlives_the_vm() -> None:
    vms, _ = await made()

    [call] = vms.created
    data = call.volumes[DATA_GUEST_PATH]
    assert (data.named, data.named_kind, data.named_mode) == (
        f"{NAME}-data",
        VolumeKind.DISK,
        NamedVolumeMode.ENSURE_EXISTS,
    )
    assert data.size_mib == DATA_MIB
