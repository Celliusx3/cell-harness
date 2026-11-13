"""What the computer server tells every bot when it connects."""

from __future__ import annotations

from mcp import Client

from computer.server import COMPUTER_INSTRUCTIONS
from tests.conftest import FakeDocker, server_with


def test_the_built_server_sends_the_pc_instructions() -> None:
    server = server_with(FakeDocker(status="missing"))

    assert server.instructions == COMPUTER_INSTRUCTIONS


async def test_a_connecting_client_receives_the_pc_instructions() -> None:
    async with Client(server_with(FakeDocker(status="missing"))) as client:
        assert client.instructions == COMPUTER_INSTRUCTIONS


def test_the_instructions_name_the_tools_and_the_computer_page() -> None:
    for name in (
        "computer__browser_navigate",
        "computer__browser_read_page",
        "computer__browser_act",
        "computer__shell",
        "Computer page",
    ):
        assert name in COMPUTER_INSTRUCTIONS


def test_the_instructions_tell_the_bot_to_ask_before_an_action_it_cannot_undo() -> None:
    assert "ask the person first" in COMPUTER_INSTRUCTIONS
    for action in ("sends", "posts", "pays", "deletes"):
        assert action in COMPUTER_INSTRUCTIONS
