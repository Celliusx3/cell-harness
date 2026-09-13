"""The multi-step loop — phase 2's end-to-end criterion and its invariants."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Sequence
from contextlib import aclosing
from dataclasses import replace

from harness.agent.events import AgentCompleted, ToolProgress, ToolResult
from harness.agent.hooks import CompletedCall, HookChain, Signature, ToolHook
from harness.agent.hooks.native.exact_failure import EXACT_FAILURE_BLOCK, ExactFailureHook
from harness.agent.loop import INTERRUPTED_RESULT, LoopAgent
from harness.llm.messages import AssistantMessage, Text, ToolCall, ToolMessage
from harness.llm.stream import Completed, TextChunk, ToolCallChunk
from harness.session.derive import derive_messages
from harness.session.log import Session
from harness.session.models import (
    StepEnd,
    StepStart,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    UserMessageEvent,
)
from harness.tools.definition import BLOCKED, Ok, ToolOutcome
from tests.unit.fakes import (
    EchoArgs,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    hanging_tool,
    raising_tool,
    reporting_tool,
)
from tests.unit.helpers import new_session, pipeline_for, unanswered_calls


def agent(client, *tools, system_prompt: str = "", hooks: HookChain | None = None) -> LoopAgent:
    return LoopAgent(
        name="t",
        model="m",
        client=client,
        tools=pipeline_for(*tools),
        system_prompt=system_prompt,
        hooks=hooks if hooks is not None else HookChain(),
    )


async def drain(gen) -> list:
    # Bounded: the loop has no step cap, so a script that never stops calling a
    # tool would otherwise hang the suite rather than fail a test.
    async with asyncio.timeout(5):
        return [event async for event in gen]


async def test_prompt_to_tool_to_answer() -> None:
    """Acceptance: prompt → model → tool call → result → model → answer, with
    every durable event in the log in order."""
    client = SteppedClient(
        calls_tool("echo", '{"value": "42"}', text="Let me check. "),
        completed("The answer is 42."),
    )
    session = new_session()

    events = await drain(agent(client, echo_tool()).run("what is it?", session=session))

    assert [type(e).__name__ for e in events] == [
        "TextChunk",
        "ToolCallChunk",
        "ToolResult",
        "TextChunk",
        "AgentCompleted",
    ]
    # Preamble from step 0 survives into the final answer.
    assert events[-1] == AgentCompleted(text="Let me check. The answer is 42.")

    kinds = [e.type for e in session.events()]
    assert kinds == [
        "turn/start",
        "user/message",
        "step/start",
        "assistant/chunk",  # the preamble text
        "assistant/chunk",  # the tool-call chunk
        "assistant/chunk",  # the Completed terminal
        "assistant/message",
        "tool/call",
        "tool/result",
        "step/end",
        "step/start",
        "assistant/chunk",
        "assistant/chunk",
        "assistant/message",
        "step/end",
        "turn/end",
    ]
    assert session.events()[-1] == TurnEnd(turn=0, reason="completed")


async def test_the_tool_result_reaches_the_model_via_the_log() -> None:
    """The discipline: step 1's request is derived, so the result got there by
    being logged rather than by the loop threading it."""
    client = SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("done"))
    session = new_session()

    await drain(agent(client, echo_tool()).run("q", session=session))

    second_request = client.seen_per_call[1]
    assert [type(m).__name__ for m in second_request] == [
        "UserMessage",
        "AssistantMessage",
        "ToolMessage",
    ]
    assert second_request[-1] == ToolMessage(tool_call_id="c1", content="42")


async def test_tool_schemas_reach_the_wire_each_step() -> None:
    client = SteppedClient(calls_tool("echo", '{"value": "x"}'), completed("done"))
    session = new_session()

    await drain(agent(client, echo_tool()).run("q", session=session))

    assert client.seen_tools is not None
    assert [s.name for s in client.seen_tools] == ["echo"]


async def test_an_agent_with_no_tools_sends_none_not_an_empty_list() -> None:
    """Some providers reject `"tools": []`, and it says something different from
    "no tools available"."""
    client = SteppedClient(completed("hi"))
    bare = LoopAgent(name="t", model="m", client=client)

    await drain(bare.run("q", session=new_session()))

    assert client.seen_tools is None


async def test_progress_interleaves_and_the_result_always_comes_last() -> None:
    """Acceptance: progress arrives during the call, never after the result."""
    client = SteppedClient(calls_tool("slow", '{"value": "done"}'), completed("ok"))
    session = new_session()
    tool = reporting_tool([(10.0, "starting"), (90.0, "nearly")])

    events = await drain(agent(client, tool).run("q", session=session))

    progress = [e for e in events if isinstance(e, ToolProgress)]
    assert [(p.percent, p.message) for p in progress] == [(10.0, "starting"), (90.0, "nearly")]
    # Every progress event precedes the single result for that call.
    result_at = next(i for i, e in enumerate(events) if isinstance(e, ToolResult))
    assert all(events.index(p) < result_at for p in progress)


async def test_progress_is_not_logged() -> None:
    """A progress reading is neither durable nor a fact about the conversation,
    so a replayed turn has none and consumers must tolerate that."""
    client = SteppedClient(calls_tool("slow", '{"value": "done"}'), completed("ok"))
    session = new_session()

    await drain(agent(client, reporting_tool([(50.0, "half")])).run("q", session=session))

    assert not any("progress" in e.type for e in session.events())


async def test_a_failing_tool_is_logged_with_its_typed_code() -> None:
    """The guardrail counts by identity; a string prefix would make a tool that
    phrased its error differently invisible to it."""
    client = SteppedClient(calls_tool("echo", "{bad json"), completed("recovered"))
    session = new_session()

    events = await drain(agent(client, echo_tool()).run("q", session=session))

    result = next(e for e in session.events() if isinstance(e, ToolResultEvent))
    assert result.error == "INVALID_ARGUMENTS"
    assert result.message.text.startswith("error: ")
    # The turn recovers: the model gets another step and answers.
    assert isinstance(events[-1], AgentCompleted)


async def interrupt_during_tool(agent_, session: Session) -> None:
    """Cancel a turn while a dispatched tool is still running.

    Cancelling the consuming task is what a closed browser tab does. It has to be
    a task rather than a `break`, because the consumer is *blocked* inside the
    tool call — there is no next event to break on.
    """

    async def consume() -> None:
        async with aclosing(agent_.run("q", session=session)) as events:
            async for _ in events:
                pass

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)  # let it reach the hanging tool
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def test_every_dispatched_call_gets_a_result_even_when_interrupted() -> None:
    """A provider rejects a history with an unanswered call outright, so an
    abandoned turn must still answer everything it asked for."""
    client = SteppedClient(calls_tool("hang", '{"value": "a"}'))
    session = new_session()

    await interrupt_during_tool(agent(client, hanging_tool()), session)

    calls = [e for e in session.events() if isinstance(e, ToolCallEvent)]
    results = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    assert len(calls) == 1
    assert len(results) == len(calls)
    assert unanswered_calls(derive_messages(session.events())) == []
    assert session.events()[-1] == TurnEnd(turn=0, reason="cancelled")


async def test_an_interrupted_call_records_a_recoverable_error() -> None:
    client = SteppedClient(calls_tool("hang", '{"value": "a"}'))
    session = new_session()

    await interrupt_during_tool(agent(client, hanging_tool()), session)

    result = next(e for e in session.events() if isinstance(e, ToolResultEvent))
    assert result.message.text == INTERRUPTED_RESULT
    assert result.error == "INTERRUPTED_BY_CRASH"


async def test_stopping_before_any_call_exists_owes_nothing() -> None:
    """Interrupting during the model stream is not the repair path: no call has
    been made, so there is nothing to answer."""
    client = SteppedClient(calls_tool("echo", '{"value": "a"}'))
    session = new_session()

    async with aclosing(agent(client, echo_tool()).run("q", session=session)) as events:
        async for event in events:
            if isinstance(event, ToolCallChunk):
                break

    assert not any(isinstance(e, ToolCallEvent) for e in session.events())
    assert not any(isinstance(e, ToolResultEvent) for e in session.events())
    assert unanswered_calls(derive_messages(session.events())) == []


async def test_steps_are_numbered_within_their_turn() -> None:
    client = SteppedClient(calls_tool("echo", '{"value": "x"}'), completed("done"))
    session = new_session()

    await drain(agent(client, echo_tool()).run("q", session=session))

    starts = [e.step for e in session.events() if isinstance(e, StepStart)]
    ends = [e.step for e in session.events() if isinstance(e, StepEnd)]
    assert starts == [0, 1]
    assert ends == [0, 1]


async def test_assistant_message_carries_the_calls_it_requested() -> None:
    """Derived history must reproduce the pairing, or the provider rejects it."""
    client = SteppedClient(calls_tool("echo", '{"value": "x"}'), completed("done"))
    session = new_session()

    await drain(agent(client, echo_tool()).run("q", session=session))

    history = derive_messages(session.events())
    assistant = next(m for m in history if isinstance(m, AssistantMessage) and m.tool_calls)
    assert [c.name for c in assistant.tool_calls] == ["echo"]
    assert unanswered_calls(history) == []


async def test_two_calls_in_one_step_both_settle() -> None:
    from harness.llm.messages import ToolCall

    first = ToolCall(id="c1", name="echo", arguments='{"value": "a"}')
    second = ToolCall(id="c2", name="echo", arguments='{"value": "b"}')
    client = SteppedClient(
        [
            ToolCallChunk(call=first),
            ToolCallChunk(call=second),
            Completed(full_text="", tool_calls=(first, second)),
        ],
        completed("done"),
    )
    session = new_session()

    events = await drain(agent(client, echo_tool()).run("q", session=session))

    results = [e for e in events if isinstance(e, ToolResult)]
    assert [(r.tool_call_id, r.content) for r in results] == [("c1", "a"), ("c2", "b")]
    assert unanswered_calls(derive_messages(session.events())) == []


async def test_the_executor_receives_a_parsed_model_not_a_raw_dict() -> None:
    """`from_model` derives the parser from the same class as the schema, so a
    tool body works with typed values rather than re-validating a dict."""
    seen: list[EchoArgs] = []

    async def execute(args, progress):
        seen.append(args)
        return Ok(content=args.value)

    tool = echo_tool()
    typed = replace(tool, execute=execute)
    client = SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("done"))

    await drain(agent(client, typed).run("q", session=new_session()))

    assert isinstance(seen[0], EchoArgs)
    assert seen[0].value == "42"


async def test_arguments_the_schema_rejects_never_reach_the_executor() -> None:
    """Validation is the boundary: a tool body must never see input its own
    model would refuse. Pydantic does not coerce an int into a str."""
    seen: list[EchoArgs] = []

    async def execute(args, progress):
        seen.append(args)
        return Ok(content=args.value)

    typed = replace(echo_tool(), execute=execute)
    client = SteppedClient(calls_tool("echo", '{"value": 42}'), completed("recovered"))

    events = await drain(agent(client, typed).run("q", session=new_session()))

    assert seen == []
    assert isinstance(events[-1], AgentCompleted)  # the model gets to try again


def test_the_unanswered_calls_assertion_actually_detects_a_gap() -> None:
    """The other tests lean on this to prove the repair path worked, so an
    assertion that silently reports everything as fine would hide the bug it
    exists to catch."""
    from harness.llm.messages import ToolCall, UserMessage

    asked = AssistantMessage(
        content="checking",
        tool_calls=(
            ToolCall(id="c1", name="echo", arguments="{}"),
            ToolCall(id="c2", name="echo", arguments="{}"),
        ),
    )
    half = [UserMessage(content="q"), asked, ToolMessage(tool_call_id="c1", content="ok")]

    assert unanswered_calls([UserMessage(content="q")]) == []
    assert unanswered_calls(half) == ["c2"]
    assert unanswered_calls([*half, ToolMessage(tool_call_id="c2", content="ok")]) == []


async def test_text_only_turns_still_work() -> None:
    """Phase 1's behaviour must survive phase 2."""
    client = SteppedClient(completed("just talking"))
    session = new_session()

    events = await drain(agent(client, echo_tool()).run("hi", session=session))

    assert events == [TextChunk(text="just talking"), AgentCompleted(text="just talking")]
    assert sum(isinstance(e, StepStart) for e in session.events()) == 1


# ── hooks ─────────────────────────────────────────────────────────────────────


class Stub(ToolHook):
    """A hook that records what it was asked and answers as told."""

    def __init__(self, *, refuse: str | None = None, note: str | None = None) -> None:
        self.refuse, self.note = refuse, note
        self.pre_seen: list[Signature] = []
        self.post_seen: list[tuple[Signature, ToolOutcome]] = []

    async def pre(self, sig: Signature, calls: Sequence[CompletedCall]) -> str | None:
        self.pre_seen.append(sig)
        return self.refuse

    async def post(
        self, sig: Signature, outcome: ToolOutcome, calls: Sequence[CompletedCall]
    ) -> str | None:
        self.post_seen.append((sig, outcome))
        return self.note


def counting(tool):
    """`tool`, with its body counted — so a refused call is provably never run."""
    runs: list[str] = []

    async def execute(args, progress):
        runs.append(args.value)
        return await tool.execute(args, progress)

    return replace(tool, execute=execute), runs


async def test_a_refused_call_is_logged_but_never_run() -> None:
    hook = Stub(refuse="not today")
    tool, runs = counting(echo_tool())
    client = SteppedClient(calls_tool("echo", '{"value": "x"}'), completed("ok"))
    session = new_session()

    events = await drain(agent(client, tool, hooks=HookChain((hook,))).run("q", session=session))

    assert runs == []
    result = next(e for e in session.events() if isinstance(e, ToolResultEvent))
    assert result.error == BLOCKED
    assert result.message.text == "error: not today"
    assert sum(isinstance(e, ToolCallEvent) for e in session.events()) == 1
    assert unanswered_calls(derive_messages(session.events())) == []
    # The post hook has nothing to annotate — the tool did not run.
    assert hook.post_seen == []
    assert isinstance(events[-1], AgentCompleted)


async def test_a_note_is_logged_as_a_guardrail_message_after_the_steps_calls() -> None:
    """Never inside the result: the tool's words stay the tool's, and a provider
    wants the tool messages directly behind the assistant that asked."""
    hook = Stub(note="think again")
    client = SteppedClient(
        [
            ToolCallChunk(call=ToolCall(id="c1", name="echo", arguments='{"value": "a"}')),
            ToolCallChunk(call=ToolCall(id="c2", name="echo", arguments='{"value": "b"}')),
            Completed(
                full_text="",
                tool_calls=[
                    ToolCall(id="c1", name="echo", arguments='{"value": "a"}'),
                    ToolCall(id="c2", name="echo", arguments='{"value": "b"}'),
                ],
            ),
        ],
        completed("ok"),
    )
    session = new_session()

    events = await drain(
        agent(client, echo_tool(), hooks=HookChain((hook,))).run("q", session=session)
    )

    kinds = [
        e.type for e in session.events() if e.type in ("tool/result", "user/message", "step/end")
    ]
    assert kinds == [
        "user/message",
        "tool/result",
        "tool/result",
        "user/message",
        "step/end",
        "step/end",
    ]
    note = [e for e in session.events() if isinstance(e, UserMessageEvent)][1]
    assert note.source == "application"
    assert note.message.content == "think again\n\nthink again"
    assert all(
        e.message.content in ((Text(text="a"),), (Text(text="b"),))
        for e in session.events()
        if isinstance(e, ToolResultEvent)
    )
    # On the wire: assistant(tool_calls) → tool → tool → user(note) → assistant.
    assert [m.role for m in derive_messages(session.events())][1:] == [
        "assistant",
        "tool",
        "tool",
        "user",
        "assistant",
    ]
    assert [e.content for e in events if isinstance(e, ToolResult)] == ["a", "b"]
    assert hook.post_seen[0][1] == Ok(content="a")


async def test_a_step_without_notes_logs_no_guardrail_message() -> None:
    client = SteppedClient(calls_tool("echo", '{"value": "x"}'), completed("ok"))
    session = new_session()

    await drain(agent(client, echo_tool(), hooks=HookChain((Stub(),))).run("q", session=session))

    assert [e.source for e in session.events() if isinstance(e, UserMessageEvent)] == ["user"]


async def test_the_fifth_identical_failing_call_is_refused_and_a_succeeding_one_never() -> None:
    """Acceptance, through the loop with the real guardrail."""
    guardrail = HookChain((ExactFailureHook(),))
    boom, runs = counting(raising_tool())
    scripts = [calls_tool("boom", '{"value": "x"}', id=f"c{i}") for i in range(EXACT_FAILURE_BLOCK)]
    session = new_session()

    events = await drain(
        agent(SteppedClient(*scripts, completed("gave up")), boom, hooks=guardrail).run(
            "q", session=session
        )
    )

    results = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    assert [r.error for r in results] == ["EXECUTION_ERROR"] * (EXACT_FAILURE_BLOCK - 1) + [BLOCKED]
    assert len(runs) == EXACT_FAILURE_BLOCK - 1
    # Warned from the second failure on, as a guardrail message on each such step.
    warned = [e for e in session.events() if isinstance(e, UserMessageEvent) and e.source != "user"]
    assert len(warned) == EXACT_FAILURE_BLOCK - 2
    assert isinstance(events[-1], AgentCompleted)

    session = new_session()
    ok = [calls_tool("echo", '{"value": "x"}', id=f"c{i}") for i in range(EXACT_FAILURE_BLOCK + 1)]
    await drain(
        agent(SteppedClient(*ok, completed("done")), echo_tool(), hooks=guardrail).run(
            "q", session=session
        )
    )

    assert all(e.error is None for e in session.events() if isinstance(e, ToolResultEvent))
