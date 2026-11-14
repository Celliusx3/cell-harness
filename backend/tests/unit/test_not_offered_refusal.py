"""A refused call says how to get the tool only to a caller that can."""

from __future__ import annotations

from harness.llm import ToolCall
from harness.tools import REFUSED, CallOrigin, Failure
from tests.unit.helpers import new_session, toolset_for

SHELL = ToolCall(id="c1", name="computer__shell", arguments="{}")
ORIGIN = CallOrigin(bot_id="b", conversation_id="s", mode="ask")


async def refusal_text(*, can_reach_servers: bool) -> str:
    toolset = toolset_for(can_reach_servers=can_reach_servers)
    outcome = await toolset.execute(
        SHELL, progress=_ignore, origin=ORIGIN, session=new_session(), sees_images=False
    )
    assert isinstance(outcome, Failure)
    assert outcome.code == REFUSED
    return outcome.message


async def _ignore(*, percent: float | None, message: str | None) -> None:
    return None


async def test_a_caller_that_cannot_reach_server_tools_is_not_sent_to_get_function_details() -> (
    None
):
    text = await refusal_text(can_reach_servers=False)

    assert "get_function_details" not in text
    assert "computer__shell" in text


async def test_a_caller_that_can_reach_server_tools_is_told_to_read_the_schema() -> None:
    assert "get_function_details" in await refusal_text(can_reach_servers=True)
