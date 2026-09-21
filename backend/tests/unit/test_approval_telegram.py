"""A gated call on Telegram: four inline buttons, and a tap that answers and edits the card."""

from __future__ import annotations

from harness.channels.telegram.asking import APPROVE_BY_LINK
from harness.channels.telegram.channel import RECEIPTS, STALE_TAP
from harness.session.models import ApprovalGrant, ToolResultEvent, TurnEnd
from harness.tools.approval import DENIED, ApprovalGate
from harness.tools.client import ClientToolService
from harness.tools.definition import Ok, ToolDefinition, ToolOutcome
from harness.web.agent import CLIENT_TOOLS
from tests.unit.fakes import EchoArgs, SteppedClient, calls_tool, completed
from tests.unit.gateway_helpers import CHAT, build, msg, settle
from tests.unit.helpers import no_skills
from tests.unit.telegram_fakes import decision_update

WRITE = "memory__write_note"


def _writer(ran: list[str]) -> ToolDefinition[EchoArgs]:
    async def execute(args: EchoArgs, _context) -> ToolOutcome:
        ran.append(args.value)
        return Ok(content=f"saved {args.value}")

    return ToolDefinition.from_model(
        name=WRITE, description="Save a note.", args_model=EchoArgs, execute=execute
    )


def _asking(tmp_path, ran: list[str], *, call_id: str = "c1"):
    gate = ApprovalGate(frozenset({WRITE}), tmp_path / "approvals.json")
    tools = ClientToolService(CLIENT_TOOLS, gate)
    model = SteppedClient(calls_tool(WRITE, '{"value": "Kopi"}', id=call_id), completed("saved"))
    return build(
        tmp_path,
        model,
        _writer(ran),
        *tools.definitions(),
        skills=no_skills(),
        client_tools=tools,
        gate=gate,
    )


async def _log(sessions, chats):
    state = await chats.load("telegram", CHAT)
    assert state is not None
    return (await sessions.read(state.conversation_id)).events()


async def test_a_gated_call_is_asked_with_four_inline_buttons(tmp_path) -> None:
    ran: list[str] = []
    bot, gateway, runs, chats, sessions = _asking(tmp_path, ran)

    await gateway.receive(msg("remember Kopi"))
    await settle(runs, gateway)

    ((chat_id, text, markup),) = bot.linked
    assert chat_id == CHAT
    assert "write note" in text and "memory" in text and "Kopi" in text
    rows = [[(b.text, b.callback_data) for b in row] for row in markup.inline_keyboard]
    assert rows == [
        [("Allow once", "ap:c1:once"), ("Allow for this conversation", "ap:c1:conversation")],
        [("Always allow", "ap:c1:always"), ("Deny", "ap:c1:deny")],
    ]
    assert ran == []
    assert (await _log(sessions, chats))[-1] == TurnEnd(turn=0, reason="pending")


async def test_a_tap_answers_the_call_and_edits_the_card_into_a_receipt(tmp_path) -> None:
    ran: list[str] = []
    bot, gateway, runs, chats, sessions = _asking(tmp_path, ran)
    channel = gateway._channels["telegram"].channel
    await gateway.receive(msg("remember Kopi"))
    await settle(runs, gateway)
    ((_, card_text, _),) = bot.linked

    tap = decision_update(CHAT, "ap:c1:conversation", card_text)
    await channel._on_decision(tap, None)
    await settle(runs, gateway)

    assert ran == ["Kopi"]
    assert tap.callback_query.answered is True
    ((edited_text, edited_markup),) = tap.callback_query.edits
    assert edited_text == f"{card_text}\n\n{RECEIPTS['conversation']}"
    assert edited_markup is None
    events = await _log(sessions, chats)
    assert ApprovalGrant(turn=1, tool=WRITE) in events
    assert events[-1] == TurnEnd(turn=1, reason="completed")
    assert bot.sent[-1] == (CHAT, "saved")


async def test_a_deny_tap_writes_the_denied_result(tmp_path) -> None:
    ran: list[str] = []
    bot, gateway, runs, chats, sessions = _asking(tmp_path, ran)
    channel = gateway._channels["telegram"].channel
    await gateway.receive(msg("remember Kopi"))
    await settle(runs, gateway)

    tap = decision_update(CHAT, "ap:c1:deny", "card")
    await channel._on_decision(tap, None)
    await settle(runs, gateway)

    assert ran == []
    result = next(e for e in await _log(sessions, chats) if isinstance(e, ToolResultEvent))
    assert result.error == DENIED
    assert tap.callback_query.edits[0][0].endswith(RECEIPTS["deny"])


async def test_a_stale_tap_is_told_so(tmp_path) -> None:
    ran: list[str] = []
    bot, gateway, runs, chats, sessions = _asking(tmp_path, ran)
    channel = gateway._channels["telegram"].channel
    await gateway.receive(msg("remember Kopi"))
    await settle(runs, gateway)
    first = decision_update(CHAT, "ap:c1:once", "card")
    await channel._on_decision(first, None)
    await settle(runs, gateway)

    second = decision_update(CHAT, "ap:c1:deny", "card")
    await channel._on_decision(second, None)
    await settle(runs, gateway)

    assert ran == ["Kopi"]
    assert second.callback_query.answered is True
    assert second.callback_query.edits == [(f"card\n\n{STALE_TAP}", None)]


async def test_a_call_id_too_long_for_a_button_is_asked_by_link(tmp_path) -> None:
    ran: list[str] = []
    long_id = "call_" + "x" * 60
    bot, gateway, runs, chats, sessions = _asking(tmp_path, ran, call_id=long_id)

    await gateway.receive(msg("remember Kopi"))
    await settle(runs, gateway)

    ((_, text, markup),) = bot.linked
    assert text == APPROVE_BY_LINK.format(label="write note")
    assert markup.inline_keyboard[0][0].url.endswith(f"/answer/c0/{long_id}")
