"""Hooks around every tool call, driven through the loop.

A refusal is logged and never run; a note is its own `application/message`
after the step's results, never inside one — the tool's words stay the tool's.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from harness.agent.events import AgentCompleted, ToolResult
from harness.agent.hooks import CompletedCall, HookChain, Signature, ToolHook
from harness.agent.hooks.native.exact_failure import EXACT_FAILURE_BLOCK, ExactFailureHook
from harness.llm.messages import Text, ToolCall
from harness.llm.stream import Completed, ToolCallChunk
from harness.session.derive import derive_messages
from harness.session.models import ApplicationMessageEvent, ToolCallEvent, ToolResultEvent
from harness.tools.definition import BLOCKED, Ok, ToolOutcome
from tests.unit.fakes import SteppedClient, calls_tool, completed, echo_tool, raising_tool
from tests.unit.helpers import drain, loop_agent, new_session, unanswered_calls


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

    events = await drain(
        loop_agent(client, tool, hooks=HookChain((hook,))).run("q", session=session)
    )

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
        loop_agent(client, echo_tool(), hooks=HookChain((hook,))).run("q", session=session)
    )

    kinds = [
        e.type
        for e in session.events()
        if e.type in ("tool/result", "user/message", "application/message", "step/end")
    ]
    assert kinds == [
        "user/message",
        "tool/result",
        "tool/result",
        "application/message",
        "step/end",
        "step/end",
    ]
    (note,) = [e for e in session.events() if isinstance(e, ApplicationMessageEvent)]
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

    await drain(
        loop_agent(client, echo_tool(), hooks=HookChain((Stub(),))).run("q", session=session)
    )

    assert not [e for e in session.events() if isinstance(e, ApplicationMessageEvent)]


async def test_the_fifth_identical_failing_call_is_refused_and_a_succeeding_one_never() -> None:
    """Acceptance, through the loop with the real guardrail."""
    guardrail = HookChain((ExactFailureHook(),))
    boom, runs = counting(raising_tool())
    scripts = [calls_tool("boom", '{"value": "x"}', id=f"c{i}") for i in range(EXACT_FAILURE_BLOCK)]
    session = new_session()

    events = await drain(
        loop_agent(SteppedClient(*scripts, completed("gave up")), boom, hooks=guardrail).run(
            "q", session=session
        )
    )

    results = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    assert [r.error for r in results] == ["EXECUTION_ERROR"] * (EXACT_FAILURE_BLOCK - 1) + [BLOCKED]
    assert len(runs) == EXACT_FAILURE_BLOCK - 1
    # Warned from the second failure on, as a guardrail message on each such step.
    warned = [e for e in session.events() if isinstance(e, ApplicationMessageEvent)]
    assert len(warned) == EXACT_FAILURE_BLOCK - 2
    assert isinstance(events[-1], AgentCompleted)

    session = new_session()
    ok = [calls_tool("echo", '{"value": "x"}', id=f"c{i}") for i in range(EXACT_FAILURE_BLOCK + 1)]
    await drain(
        loop_agent(SteppedClient(*ok, completed("done")), echo_tool(), hooks=guardrail).run(
            "q", session=session
        )
    )

    assert all(e.error is None for e in session.events() if isinstance(e, ToolResultEvent))
