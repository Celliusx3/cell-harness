"""The phone reaches DNS and the public internet, and never the Mac or the person's own network."""

from __future__ import annotations

import pytest
from microsandbox import Action, DestGroup, Destination, Rule

from phone.engines.microsandbox import phone_network_policy
from tests.unit.test_microsandbox_engine import made

POLICY = phone_network_policy()


def test_egress_no_rule_allows_is_denied() -> None:
    assert POLICY.default_egress == Action.DENY


def test_the_phone_resolves_names_and_reaches_public_addresses_only() -> None:
    assert POLICY.rules == (
        *Rule.allow_dns(),
        Rule.allow(destination=Destination.group(DestGroup.PUBLIC)),
    )


@pytest.mark.parametrize(
    "group",
    [
        DestGroup.HOST,
        DestGroup.LOOPBACK,
        DestGroup.PRIVATE,
        DestGroup.LINK_LOCAL,
        DestGroup.METADATA,
        DestGroup.MULTICAST,
    ],
)
def test_no_rule_beyond_dns_lets_the_phone_reach_a_non_public_group(group: DestGroup) -> None:
    beyond_dns = POLICY.rules[len(Rule.allow_dns()) :]

    assert all(rule.destination != Destination.group(group) for rule in beyond_dns)


async def test_the_phone_is_made_with_that_policy() -> None:
    vms, _ = await made()

    [call] = vms.created
    assert call.network.policy == POLICY
