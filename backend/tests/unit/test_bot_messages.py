"""A bot's message: its hop and answer read from the log, its wording, and how it is offered."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.bots import BotDraft, BotService
from harness.llm.messages import AssistantMessage, UserMessage
from harness.runs.bot_messages import MAX_HOPS, final_reply, hop_of_last_turn
from harness.session.derive import derive_messages
from harness.session.models import (
    AssistantMessageEvent,
    BotMessage,
    BotMessageEvent,
    SessionEvent,
    TurnEnd,
    TurnEndReason,
    TurnStart,
    UserMessageEvent,
)
from harness.tools.definition import Failure, Ok
from harness.tools.native.bots import MESSAGE_BOT, message_bot_tool
from harness.web.runtime import DEFAULT_TOOLS, NOT_CALLABLE_FROM_SCRIPTS, SUBAGENT_TOOLS
from tests.unit.helpers import durable_service

CONFIG = Path(__file__).resolve().parents[2] / "config.json"
ASKED = BotMessage(
    from_bot_id="a", from_name="Assistant", text="Is B still true?", hop=3, intent="request"
)
ANSWERED = BotMessage(from_bot_id="r", from_name="Researcher", text="Yes.", hop=4, intent="result")


def opened_by_bot(turn: int, message: BotMessage) -> list[SessionEvent]:
    return [TurnStart(turn=turn, bot_id="r"), BotMessageEvent(turn=turn, message=message)]


def opened_by_person(turn: int) -> list[SessionEvent]:
    return [
        TurnStart(turn=turn, bot_id="r"),
        UserMessageEvent(turn=turn, message=UserMessage(content="hi")),
    ]


def ended(turn: int, said: str, reason: TurnEndReason = "completed") -> list[SessionEvent]:
    return [
        AssistantMessageEvent(turn=turn, step=0, message=AssistantMessage(content=said)),
        TurnEnd(turn=turn, reason=reason),
    ]


class Unsent:
    """A sender the tests never reach."""

    async def send(
        self, call_id: str, *, from_bot_id: str, to_name: str, text: str
    ) -> Ok | Failure:
        raise AssertionError("not sent")


def test_a_turn_the_person_opened_is_hop_zero() -> None:
    assert hop_of_last_turn(opened_by_person(0)) == 0


def test_a_turn_a_bot_message_opened_has_that_message_s_hop() -> None:
    log = [*opened_by_person(0), *ended(0, "x"), *opened_by_bot(1, ASKED)]

    assert hop_of_last_turn(log) == 3


def test_a_turn_the_person_opens_after_a_chain_starts_again_at_zero() -> None:
    log = [*opened_by_bot(0, ASKED), *ended(0, "x"), *opened_by_person(1)]

    assert hop_of_last_turn(log) == 0


def test_a_chain_may_run_to_six_hops() -> None:
    assert MAX_HOPS == 6


def test_the_answer_is_what_the_last_turn_ended_by_saying() -> None:
    log = [
        *opened_by_bot(0, ASKED),
        AssistantMessageEvent(turn=0, step=0, message=AssistantMessage(content="Checking.")),
        *ended(0, "Yes, B is current."),
    ]

    assert final_reply(log, "Researcher") == "Yes, B is current."


@pytest.mark.parametrize(
    ("reason", "answer"),
    [
        ("pending", "Researcher is waiting for the user to answer it in its own chat."),
        ("failed", "Researcher stopped before it finished, and has no answer."),
        ("cancelled", "Researcher stopped before it finished, and has no answer."),
    ],
)
def test_a_turn_that_did_not_complete_answers_why(reason: TurnEndReason, answer: str) -> None:
    log = [*opened_by_bot(0, ASKED), *ended(0, "half a thought", reason)]

    assert final_reply(log, "Researcher") == answer


def test_a_request_reads_as_another_bot_s_whose_answer_goes_back() -> None:
    assert derive_messages(opened_by_bot(0, ASKED)) == [
        UserMessage(
            content='<message from="Assistant">\nIs B still true?\n</message>\n'
            "Assistant is another of the user's bots, not the user. Do what it asks. Your final "
            "reply is sent back to Assistant on its own, so write it for Assistant."
        )
    ]


def test_an_answer_reads_as_one_to_pass_on_and_not_send_back() -> None:
    assert derive_messages(opened_by_bot(0, ANSWERED)) == [
        UserMessage(
            content='<message from="Researcher">\nYes.\n</message>\n'
            "This is Researcher's answer to the message you sent it with message_bot. Tell the "
            "user what it means for them. Your reply is not sent back to Researcher."
        )
    ]


async def test_the_bot_argument_lists_the_active_bots_by_name(tmp_path: Path) -> None:
    store = BotService(
        tmp_path / "bots.json", durable_service(tmp_path / "sessions"), assistant_instructions="A."
    )
    await store.create(BotDraft(name="Researcher", instructions="Cite."))
    gone = await store.create(BotDraft(name="Writer", instructions="Write."))
    store.archive(gone.id)

    schema = message_bot_tool(store, Unsent()).spec().input_schema

    assert schema["properties"]["bot"]["enum"] == ["Assistant", "Bot builder", "Researcher"]
    assert sorted(schema["required"]) == ["bot", "message"]


def test_the_main_chat_is_offered_it_and_scripts_and_helpers_are_not() -> None:
    assert MESSAGE_BOT in DEFAULT_TOOLS
    assert MESSAGE_BOT in NOT_CALLABLE_FROM_SCRIPTS
    assert MESSAGE_BOT not in SUBAGENT_TOOLS


def test_the_committed_config_sends_a_message_without_asking() -> None:
    committed = json.loads(CONFIG.read_text())

    assert MESSAGE_BOT not in committed["approval"]["tools"]
