"""`/mode` read from Telegram, and what it does to a chat through the gateway."""

from __future__ import annotations

import pytest

from harness.channels.commands import ModeCommand, apply
from harness.channels.telegram.commands import parse
from harness.tools import ApprovalService, Ok, Tool, ToolOutcome
from tests.unit.fakes import EchoArgs, SteppedClient, calls_tool, completed
from tests.unit.gateway_helpers import CHAT, build, msg, settle
from tests.unit.helpers import no_skills

SAVE = "save_note"


@pytest.mark.parametrize(
    ("text", "word"),
    [("/mode", ""), ("/mode auto", "auto"), ("/MODE Ask", "ask"), ("/mode@my_bot yes", "yes")],
)
def test_mode_and_its_word_are_read(text: str, word: str) -> None:
    assert parse(text) == ModeCommand(word=word)


def _saver(ran: list[str]) -> Tool[EchoArgs]:
    async def execute(args: EchoArgs, _context) -> ToolOutcome:
        ran.append(args.value)
        return Ok(content=f"saved {args.value}")

    return Tool.from_model(name=SAVE, description="Save.", args_model=EchoArgs, execute=execute)


async def _gateway(tmp_path, ran: list[str]):
    approvals = ApprovalService(
        frozenset({SAVE}), frozenset, tmp_path / "approvals.json", default_mode="ask"
    )
    model = SteppedClient(calls_tool(SAVE, '{"value": "Kopi"}'), completed("saved"))
    _, gateway, runs, _, _ = await build(
        tmp_path, model, _saver(ran), skills=no_skills(), approvals=approvals
    )
    return gateway, runs


async def test_mode_alone_names_the_mode_on(tmp_path) -> None:
    gateway, _ = await _gateway(tmp_path, [])

    assert await apply(gateway, "telegram", CHAT, ModeCommand(word="")) == "Mode: Ask."
    await gateway.aclose()


async def test_mode_auto_lets_the_next_protected_call_run(tmp_path) -> None:
    ran: list[str] = []
    gateway, runs = await _gateway(tmp_path, ran)

    reply = await apply(gateway, "telegram", CHAT, ModeCommand(word="auto"))
    await gateway.receive(msg("remember Kopi"))
    await settle(runs, gateway)

    assert reply == "Mode: Auto."
    assert ran == ["Kopi"]
    assert await apply(gateway, "telegram", CHAT, ModeCommand(word="")) == "Mode: Auto."
    await gateway.aclose()


async def test_any_other_word_says_which_words_mode_takes(tmp_path) -> None:
    gateway, _ = await _gateway(tmp_path, [])

    reply = await apply(gateway, "telegram", CHAT, ModeCommand(word="yes"))

    assert reply == "Use /mode ask or /mode auto. Mode: Ask."
    await gateway.aclose()
