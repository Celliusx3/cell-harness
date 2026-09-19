"""The loop guardrail's detectors as pure folds over one turn's log."""

from __future__ import annotations

from harness.agent.hooks import HookChain
from harness.agent.hooks.native.exact_failure import EXACT_FAILURE_BLOCK
from harness.agent.hooks.native.no_progress import NO_PROGRESS_BLOCK
from harness.agent.hooks.native.same_tool_failure import (
    SAME_TOOL_FAILURE_BLOCK,
)
from harness.llm.messages import ToolCall, ToolMessage
from harness.session.log import Session
from harness.session.models import ToolCallEvent, ToolResultEvent, TurnStart
from harness.tools.definition import BLOCKED, EXECUTION_ERROR, REFUSED, Failure, Ok
from harness.web.agent import default_hooks
from tests.unit.helpers import new_session

GUARD = default_hooks()


def call(name: str = "read", arguments: str = '{"a": 1}', *, id: str = "c") -> ToolCall:
    return ToolCall(id=id, name=name, arguments=arguments)


def settle(
    session: Session,
    name: str = "read",
    arguments: str = '{"a": 1}',
    *,
    text: str = "same",
    error: str | None = None,
) -> None:
    """Append one call and its result to the current turn."""
    id = f"c{len(session.events())}"
    session.append(ToolCallEvent(turn=0, step=0, call=call(name, arguments, id=id)))
    session.append(
        ToolResultEvent(
            turn=0, step=0, message=ToolMessage(tool_call_id=id, content=text), error=error
        )
    )


def turn() -> Session:
    session = new_session()
    session.append(TurnStart(turn=0))
    return session


def failing(session: Session, times: int, name: str = "read", arguments: str = '{"a": 1}') -> None:
    for _ in range(times):
        settle(session, name, arguments, text="error: boom", error=EXECUTION_ERROR)


async def pre(guard: HookChain, session: Session, c: ToolCall | None = None) -> str | None:
    return await guard.pre_tool_call(c or call(), session=session)


async def post(
    guard: HookChain, session: Session, outcome: Ok | Failure, c: ToolCall | None = None
) -> str | None:
    return await guard.post_tool_call(c or call(), outcome, session=session)


async def test_a_first_failure_says_nothing() -> None:
    session = turn()

    assert await pre(GUARD, session) is None
    assert await post(GUARD, session, Failure(EXECUTION_ERROR, "boom")) is None


async def test_the_second_identical_failure_is_warned_with_its_count() -> None:
    session = turn()
    failing(session, 1)

    note = await post(GUARD, session, Failure(EXECUTION_ERROR, "boom"))

    assert note is not None and "2 times" in note


async def test_the_fifth_identical_failing_call_is_refused_before_it_runs() -> None:
    session = turn()
    failing(session, EXACT_FAILURE_BLOCK - 2)
    assert await pre(GUARD, session) is None

    failing(session, 1)
    reason = await pre(GUARD, session)

    assert reason is not None
    assert "4 times" in reason
    assert "was not run" in reason


async def test_a_refusal_carries_the_last_failures_own_advice() -> None:
    session = turn()
    for _ in range(EXACT_FAILURE_BLOCK - 1):
        settle(session, text="error: read its schema with get_function_details", error=REFUSED)

    reason = await pre(GUARD, session)

    assert reason is not None and "read its schema with get_function_details" in reason


async def test_a_success_resets_the_failure_count() -> None:
    session = turn()
    failing(session, EXACT_FAILURE_BLOCK - 1)
    settle(session, text="fixed")
    failing(session, 1)

    assert await pre(GUARD, session) is None


async def test_a_succeeding_call_is_never_refused() -> None:
    session = turn()
    for i in range(20):
        settle(session, "write", text=f"result {i}")

    assert await pre(GUARD, session, call("write")) is None


async def test_the_guardrails_own_refusals_are_not_counted() -> None:
    session = turn()
    failing(session, EXACT_FAILURE_BLOCK - 1)
    settle(session, text="error: was not run", error=BLOCKED)
    settle(session, text="error: was not run", error=BLOCKED)

    reason = await pre(GUARD, session)

    assert reason is not None and f"{EXACT_FAILURE_BLOCK - 1} times" in reason


async def test_the_same_tool_failing_with_different_arguments_is_warned_at_three() -> None:
    session = turn()
    failing(session, 1, arguments='{"a": 1}')
    failing(session, 1, arguments='{"a": 2}')

    note = await post(GUARD, session, Failure(EXECUTION_ERROR, "boom"), call(arguments='{"a": 3}'))

    assert note is not None and "3 times" in note and "different arguments" in note


async def test_the_eighth_failure_of_one_tool_is_refused_whatever_the_arguments() -> None:
    session = turn()
    for i in range(SAME_TOOL_FAILURE_BLOCK - 1):
        failing(session, 1, arguments=f'{{"a": {i}}}')

    reason = await pre(GUARD, session, call(arguments='{"a": 99}'))

    assert reason is not None and "different arguments" in reason


async def test_another_tools_failures_do_not_count() -> None:
    session = turn()
    failing(session, SAME_TOOL_FAILURE_BLOCK, name="other")

    assert await pre(GUARD, session) is None


async def test_an_identical_result_twice_is_warned() -> None:
    session = turn()
    settle(session, "write", text="same")

    note = await post(GUARD, session, Ok(content="same"), call("write"))

    assert note is not None and "identical" in note and "2 times" in note


async def test_a_different_result_is_progress() -> None:
    session = turn()
    settle(session, text="same")
    settle(session, text="same")

    note = await post(GUARD, session, Ok(content="different"))

    assert note is None or "identical" not in note


async def test_the_fifth_identical_call_is_refused_whatever_the_tool() -> None:
    session = turn()
    for _ in range(NO_PROGRESS_BLOCK - 1):
        settle(session, "read", text="same")
        settle(session, "write", text="same")

    for name in ("read", "write"):
        reason = await pre(GUARD, session, call(name))
        assert reason is not None and "identical result" in reason and "was not run" in reason


async def test_the_fourth_identical_call_still_runs() -> None:
    session = turn()
    for _ in range(NO_PROGRESS_BLOCK - 2):
        settle(session, text="same")

    assert await pre(GUARD, session) is None


async def test_consecutive_calls_with_changing_results_are_noted_at_three_five_and_eight() -> None:
    session = turn()
    noted: list[int] = []
    for i in range(1, 10):
        outcome = Ok(content=f"poll {i}")
        if await post(GUARD, session, outcome, call("write")) is not None:
            noted.append(i)
        settle(session, "write", text=f"poll {i}")

    assert noted == [3, 5, 8]


async def test_an_intervening_call_breaks_the_run() -> None:
    session = turn()
    settle(session, "write", text="1")
    settle(session, "write", text="2")
    settle(session, "other", text="x")

    assert await post(GUARD, session, Ok(content="3"), call("write")) is None


async def test_an_earlier_turns_failures_do_not_count() -> None:
    session = turn()
    failing(session, EXACT_FAILURE_BLOCK)
    session.append(TurnStart(turn=1))

    assert await pre(GUARD, session) is None


async def test_the_call_in_flight_has_no_result_and_is_ignored() -> None:
    session = turn()
    failing(session, EXACT_FAILURE_BLOCK - 2)
    session.append(ToolCallEvent(turn=0, step=0, call=call(id="running")))

    assert await pre(GUARD, session, call(id="running")) is None


async def test_arguments_are_compared_by_value_not_spelling() -> None:
    session = turn()
    failing(session, EXACT_FAILURE_BLOCK - 1, arguments='{"b": 2, "a": 1}')

    assert await pre(GUARD, session, call(arguments='{"a":1,"b":2}')) is not None


async def test_empty_arguments_are_an_empty_object() -> None:
    session = turn()
    failing(session, EXACT_FAILURE_BLOCK - 1, arguments="{}")

    assert await pre(GUARD, session, call(arguments="")) is not None


async def test_unparsable_arguments_still_compare_as_text() -> None:
    session = turn()
    failing(session, EXACT_FAILURE_BLOCK - 1, arguments="not json")

    assert await pre(GUARD, session, call(arguments="not json")) is not None
