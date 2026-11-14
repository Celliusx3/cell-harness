"""A worker's question says how the person answers it, and a mismatch is a typed failure."""

from __future__ import annotations

import json

import pytest

from harness.llm import ToolCall, ToolMessage
from harness.runtime.events import AgentCompleted
from harness.session.domain.models import ToolCallEvent, ToolResultEvent, TurnStart
from harness.tickets.service.worker import kept_report, worker_end
from harness.tools import Failure, Ok
from harness.tools.domain.outcome import INVALID_ARGUMENTS
from harness.tools.native.tickets import TICKET_REPORT, ticket_report_tool
from tests.unit.helpers import context_for

QUESTION = "Which airline?"
SITE = {"origin": "https://api.example.com", "auth": "bearer"}


async def reported(**fields: object) -> Ok | Failure:
    arguments = {"state": "blocked", "summary": "Needs a choice.", **fields}
    return await ticket_report_tool().invoke(json.dumps(arguments), context=context_for())


@pytest.mark.parametrize(
    "fields",
    [
        {"question": QUESTION},
        {"question": QUESTION, "ask": "choice", "options": ["ANA", "JAL"]},
        {"question": QUESTION, "ask": "location"},
        {"question": QUESTION, "ask": "takeover"},
        {
            "question": QUESTION,
            "ask": "secret",
            "secret_name": "flights_key",
            "secret_destination": SITE,
        },
    ],
    ids=["text", "choice", "location", "takeover", "secret"],
)
async def test_each_way_of_asking_is_accepted(fields: dict[str, object]) -> None:
    assert isinstance(await reported(**fields), Ok)


@pytest.mark.parametrize(
    "fields",
    [
        {"question": QUESTION, "ask": "choice"},
        {"question": QUESTION, "ask": "text", "options": ["ANA", "JAL"]},
        {"question": QUESTION, "ask": "location", "options": ["ANA", "JAL"]},
        {"question": QUESTION, "ask": "secret", "secret_destination": SITE},
        {"question": QUESTION, "ask": "secret", "secret_name": "flights_key"},
        {"question": QUESTION, "ask": "text", "secret_name": "flights_key"},
        {"ask": "choice", "options": ["ANA", "JAL"]},
        {"ask": "location"},
        {"ask": "secret", "secret_name": "flights_key", "secret_destination": SITE},
        {"question": QUESTION, "ask": "choice", "options": ["ANA"]},
        {"question": QUESTION, "ask": "choice", "options": ["a", "b", "c", "d", "e"]},
        {"question": QUESTION, "ask": "choice", "options": ["ANA", ""]},
        {
            "question": QUESTION,
            "ask": "secret",
            "secret_name": "Bad Name",
            "secret_destination": SITE,
        },
    ],
    ids=[
        "choice-without-options",
        "options-with-text",
        "options-with-location",
        "secret-without-name",
        "secret-without-destination",
        "name-with-text",
        "choice-without-question",
        "location-without-question",
        "secret-without-question",
        "one-option",
        "five-options",
        "empty-option",
        "unnamable-secret",
    ],
)
async def test_a_mismatch_is_invalid_arguments(fields: dict[str, object]) -> None:
    outcome = await reported(**fields)

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS


def test_the_fold_carries_how_the_question_is_answered() -> None:
    arguments = json.dumps(
        {
            "state": "blocked",
            "summary": "Needs a choice.",
            "question": QUESTION,
            "ask": "choice",
            "options": ["ANA", "JAL"],
        }
    )
    events = [
        TurnStart(turn=0, bot_id="b"),
        ToolCallEvent(
            turn=0, step=0, call=ToolCall(id="r1", name=TICKET_REPORT, arguments=arguments)
        ),
        ToolResultEvent(
            turn=0, step=0, message=ToolMessage(tool_call_id="r1", content="Reported.")
        ),
    ]

    end = worker_end(AgentCompleted(text="Asked."), kept_report(events))

    assert (end.question, end.ask, end.options, end.secret_name) == (
        QUESTION,
        "choice",
        ("ANA", "JAL"),
        None,
    )
