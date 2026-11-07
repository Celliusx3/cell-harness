"""The PC reaches public addresses, and the Mac only on the ports its skills' programs listen on."""

from __future__ import annotations

import dataclasses

import pytest
from microsandbox import Action, DestGroup, Destination, Network, Protocol, Rule

from computer.engines.microsandbox import MicrosandboxEngine, pc_network_policy
from computer.machine import Machine, pc_spec
from tests.conftest import API_TOKEN, Dial, config
from tests.fake_microsandbox import FakeImages, FakeSandboxes

HOST_SERVICE_PORTS = (41000, 52000)
SPEC = pc_spec(config(), API_TOKEN, HOST_SERVICE_PORTS)
POLICY = pc_network_policy(HOST_SERVICE_PORTS)
PUBLIC = Destination.group(DestGroup.PUBLIC)
HOST = Destination.group(DestGroup.HOST)


def test_egress_no_rule_allows_is_denied_and_published_ports_stay_reachable() -> None:
    assert (POLICY.default_egress, POLICY.default_ingress) == (Action.DENY, Action.ALLOW)


def test_the_pc_resolves_names_through_the_gateway_and_reaches_the_public_internet() -> None:
    assert POLICY.rules[:3] == (*Rule.allow_dns(), Rule.allow(destination=PUBLIC))


def test_the_mac_is_allowed_only_on_each_host_service_port_over_tcp() -> None:
    assert POLICY.rules[3:] == (
        Rule.allow(destination=HOST, protocol=Protocol.TCP, port=41000),
        Rule.allow(destination=HOST, protocol=Protocol.TCP, port=52000),
    )


def test_without_host_services_the_mac_is_reached_only_for_dns() -> None:
    host_rules = [rule for rule in pc_network_policy(()).rules if rule.destination == HOST]

    assert host_rules == list(Rule.allow_dns())


def test_every_rule_allows_and_none_reaches_the_mac_on_any_port() -> None:
    assert all(rule.action == Action.ALLOW for rule in POLICY.rules)
    assert all(rule.port is not None for rule in POLICY.rules if rule.destination == HOST)


@pytest.mark.parametrize(
    "group",
    [
        DestGroup.LOOPBACK,
        DestGroup.PRIVATE,
        DestGroup.LINK_LOCAL,
        DestGroup.METADATA,
        DestGroup.MULTICAST,
    ],
)
def test_no_rule_lets_the_pc_reach_a_non_public_group(group: DestGroup) -> None:
    assert all(rule.destination != Destination.group(group) for rule in POLICY.rules)


async def test_the_pc_is_made_with_the_policy_for_its_host_service_ports() -> None:
    vms = FakeSandboxes()

    await MicrosandboxEngine(sandboxes=vms, images=FakeImages()).create(SPEC)

    assert vms.created[0].network == Network(policy=POLICY)


async def test_a_pc_made_for_other_host_service_ports_is_replaced() -> None:
    engine = MicrosandboxEngine(sandboxes=FakeSandboxes(), images=FakeImages())
    await engine.create(SPEC)

    assert await engine.replacement_reason(SPEC) is None
    assert await engine.replacement_reason(
        dataclasses.replace(SPEC, host_service_ports=(41000,))
    ) == ("its published ports, shared folders or network rules are not the spec's")


async def test_the_machine_makes_the_pc_with_the_host_service_ports_it_was_given() -> None:
    vms = FakeSandboxes()
    machine = Machine(
        engine=MicrosandboxEngine(sandboxes=vms, images=FakeImages()),
        config=config(),
        clock=Dial().clock,
        host_service_ports=HOST_SERVICE_PORTS,
    )

    async with machine.serving(), machine.in_use():
        pass

    assert vms.created[0].network == Network(policy=POLICY)
