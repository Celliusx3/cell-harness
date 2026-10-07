"""A long tool result reaches the model cut to a budget, while the log keeps every character."""

from __future__ import annotations

from contextlib import aclosing

from harness.llm.messages import Text, ToolMessage, ToolReference
from harness.session.derive import RESULT_LIMIT, derive_messages
from harness.session.models import ToolResultEvent
from harness.tools.definition import Ok, ToolDefinition
from tests.unit.fakes import EchoArgs, SteppedClient, calls_tool, completed
from tests.unit.helpers import new_session, runtime_over


def _result(*blocks: Text | ToolReference) -> ToolResultEvent:
    return ToolResultEvent(
        turn=0, step=0, message=ToolMessage(tool_call_id="c1", content=tuple(blocks))
    )


def _seen(event: ToolResultEvent) -> tuple[Text | ToolReference, ...]:
    (message,) = derive_messages([event])
    assert isinstance(message, ToolMessage)
    return message.content


def test_the_limit_is_twelve_thousand_characters() -> None:
    assert RESULT_LIMIT == 12_000


def test_a_long_result_keeps_its_head_and_says_how_much_was_cut() -> None:
    (block,) = _seen(_result(Text(text="x" * 32_060)))

    assert isinstance(block, Text)
    assert block.text.startswith("x" * RESULT_LIMIT)
    assert not block.text.startswith("x" * (RESULT_LIMIT + 1))
    assert "32,060" in block.text
    assert len(block.text) < RESULT_LIMIT + 300


def test_a_result_at_the_limit_is_untouched() -> None:
    event = _result(Text(text="x" * RESULT_LIMIT))

    assert _seen(event) == event.message.content


def test_text_parts_share_one_budget_and_references_stay() -> None:
    reference = ToolReference(tool_name="markets__get_quote")

    first, kept, second = _seen(_result(Text(text="a" * 8_000), reference, Text(text="b" * 8_000)))

    assert first == Text(text="a" * 8_000)
    assert kept == reference
    assert isinstance(second, Text)
    assert second.text.startswith("b" * 4_000)
    assert not second.text.startswith("b" * 4_001)
    assert "16,000" in second.text


def test_text_past_the_budget_is_dropped_but_references_stay() -> None:
    reference = ToolReference(tool_name="markets__get_quote")

    seen = _seen(_result(Text(text="a" * 13_000), Text(text="b" * 10), reference))

    assert [type(block) for block in seen] == [Text, ToolReference]
    assert seen[1] == reference


async def test_the_log_keeps_the_whole_result_and_the_model_sees_the_cut() -> None:
    async def execute(args: EchoArgs, context) -> Ok:
        return Ok("y" * 20_000)

    big = ToolDefinition.from_model(
        name="big", description="A long answer.", args_model=EchoArgs, execute=execute
    )
    client = SteppedClient(calls_tool("big", '{"value": "v"}'), completed("done"))
    session = new_session()

    async with aclosing(runtime_over(client, big).run("go", session=session)) as events:
        async for _ in events:
            pass

    stored = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    assert stored[0].message.content == (Text(text="y" * 20_000),)
    sent = [m for m in client.seen_per_call[1] if isinstance(m, ToolMessage)]
    assert sent[0].content[0].text.startswith("y" * RESULT_LIMIT)
    assert "20,000" in sent[0].content[0].text
