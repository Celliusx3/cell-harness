"""`hand_over` — offered by default as a client tool, its step bounded, its answer read back."""

from __future__ import annotations

import json

import pytest

from harness.tools import INVALID_ARGUMENTS, Failure, Ok, Pending, ToolDefinition
from harness.tools.native.hand_over import HAND_OVER
from harness.tools.native.hand_over.models import STEP_MAX_LENGTH
from harness.web.runtime import CLIENT_TOOLS, DEFAULT_TOOLS, NOT_CALLABLE_FROM_SCRIPTS
from tests.unit.helpers import client_tools, context_for


def _hand_over_tool() -> ToolDefinition:
    return {tool.name: tool for tool in client_tools().definitions()}[HAND_OVER]


def test_the_main_chat_is_offered_hand_over_as_a_client_tool_and_scripts_are_not() -> None:
    assert HAND_OVER in CLIENT_TOOLS.names
    assert HAND_OVER in DEFAULT_TOOLS
    assert HAND_OVER in NOT_CALLABLE_FROM_SCRIPTS


async def test_a_call_with_a_step_waits_on_the_person() -> None:
    longest = json.dumps({"step": "s" * STEP_MAX_LENGTH})

    outcome = await _hand_over_tool().invoke(longest, context=context_for())

    assert outcome == Pending()


@pytest.mark.parametrize("step", ["", "s" * (STEP_MAX_LENGTH + 1)], ids=["empty", "overlong"])
async def test_an_empty_or_overlong_step_is_invalid_arguments(step: str) -> None:
    outcome = await _hand_over_tool().invoke(json.dumps({"step": step}), context=context_for())

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS


@pytest.mark.parametrize(
    ("finished", "read"), [(True, '{"finished":true}'), (False, '{"finished":false}')]
)
def test_the_model_reads_whether_the_person_finished(finished: bool, read: str) -> None:
    output = CLIENT_TOOLS.parse(HAND_OVER, {"kind": "shared", "data": {"finished": finished}})

    assert CLIENT_TOOLS.outcome(output) == Ok(content=read)
