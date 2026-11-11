"""The phone's screen gateway is published on loopback, and a phone made without it is replaced."""

from __future__ import annotations

import dataclasses
import json

import pytest

from phone.models.errors import EngineError
from phone.services.machine import GATEWAY_PORT
from tests.fakes import NAME
from tests.unit.test_microsandbox_engine import SPEC, engine_of, made


async def test_only_the_gateway_is_published_on_a_free_loopback_port() -> None:
    vms, _ = await made()

    (port,) = vms.created[0].ports
    assert (port.guest_port, port.bind) == (GATEWAY_PORT, "127.0.0.1")
    assert port.host_port > 0


async def test_the_host_port_is_read_back_from_the_vm() -> None:
    vms, engine = await made()

    assert await engine.host_port(NAME, GATEWAY_PORT) == vms.created[0].ports[0].host_port


async def test_a_port_not_published_on_loopback_is_refused() -> None:
    vms, engine = await made()
    vms.raw_config = json.dumps(vms.stored[NAME].config).replace("127.0.0.1", "0.0.0.0")

    with pytest.raises(EngineError, match="port 6080 is not published on 127.0.0.1"):
        await engine.host_port(NAME, GATEWAY_PORT)


async def test_the_phone_made_from_the_spec_needs_no_replacing() -> None:
    _, engine = await made()

    assert await engine.replacement_reason(SPEC) is None


async def test_a_phone_made_with_other_ports_is_replaced() -> None:
    _, engine = await made()

    changed = dataclasses.replace(SPEC, published_ports=(GATEWAY_PORT, 5900))
    assert await engine.replacement_reason(changed) == (
        "its published ports or network rules are not the spec's"
    )


async def test_a_phone_made_before_the_gateway_was_published_is_replaced() -> None:
    vms, engine = await made()
    vms.stored[NAME].config["labels"] = {"cell-harness.phone": NAME}
    vms.stored[NAME].config["network"] = {"enabled": True, "ports": []}

    assert await engine.replacement_reason(SPEC) is not None


async def test_a_running_phone_is_stopped_then_removed() -> None:
    vms, engine = await made()

    await engine.remove(NAME)

    assert await engine.state(NAME) == "missing"
    assert vms.calls == ["create", "stop", "remove"]


async def test_a_stopped_phone_is_removed_without_stopping_it_again() -> None:
    vms, engine = await made()
    await engine.stop(NAME)

    await engine.remove(NAME)

    assert vms.calls == ["create", "stop", "remove"]


async def test_removing_a_phone_that_was_never_made_is_an_engine_error() -> None:
    _, engine = engine_of()

    with pytest.raises(EngineError, match="microsandbox remove failed: sandbox not found"):
        await engine.remove(NAME)
