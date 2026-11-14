"""A turn reads what the person sent while it ran at its next step, and before it ends."""

from __future__ import annotations

from harness.llm import Failed, UserMessage
from harness.runtime.events import AgentCompleted, AgentFailed, AgentPending
from harness.runtime.inbox import NO_INBOX, WaitingMessages
from harness.runtime.run_to_end import HelperTurn, run_to_end
from harness.runtime.service import Runtime
from harness.session.domain.log import Session
from tests.unit.fakes import OneModel, SteppedClient, calls_tool, completed, echo_tool, pending_tool
from tests.unit.helpers import drain, durable_service, new_session, no_images, runtime_over


class HeldInbox:
    """Holds `waiting` for the first claim, and notes the last event logged at every claim."""

    def __init__(self, session: Session, *waiting: WaitingMessages) -> None:
        self._session = session
        self._waiting = list(waiting)
        self.claimed_after: list[str] = []

    async def claim(self, conversation_id: str) -> WaitingMessages | None:
        assert conversation_id == self._session.id
        self.claimed_after.append(self._session.events()[-1].type)
        return self._waiting.pop(0) if self._waiting else None


def said(session: Session) -> list[tuple[int, str]]:
    return [(e.turn, e.message.content) for e in session.events() if e.type == "user/message"]


async def test_what_waits_is_read_at_the_next_step_boundary() -> None:
    client = SteppedClient(calls_tool("echo", '{"value": "x"}'), completed("adjusted"))
    session = new_session()
    inbox = HeldInbox(session, WaitingMessages(text="only two days", files=()))
    runtime = runtime_over(client, echo_tool(), inbox=inbox)

    events = await drain(runtime.run("plan my trip", session=session, bot_id="b"))

    assert events[-1] == AgentCompleted(text="adjusted")
    assert said(session) == [(0, "plan my trip"), (0, "only two days")]
    assert inbox.claimed_after == ["step/start", "assistant/message"]
    assert UserMessage(content="only two days") in client.seen_per_call[1]


async def test_what_waits_when_the_turn_would_complete_runs_another_step() -> None:
    client = SteppedClient(completed("first"), completed("second"))
    session = new_session()
    inbox = HeldInbox(session, WaitingMessages(text="and also", files=()))

    events = await drain(runtime_over(client, inbox=inbox).run("hi", session=session, bot_id="b"))

    assert events[-1] == AgentCompleted(text="second")
    assert said(session) == [(0, "hi"), (0, "and also")]
    assert client.calls == 2
    ends = [e.reason for e in session.events() if e.type == "turn/end"]
    assert ends == ["completed"]


async def test_the_first_step_claims_nothing() -> None:
    session = new_session()
    inbox = HeldInbox(session)
    runtime = runtime_over(SteppedClient(completed("hello")), inbox=inbox)

    await drain(runtime.run("hi", session=session, bot_id="b"))

    assert inbox.claimed_after == ["assistant/message"]


async def test_a_turn_that_fails_or_waits_claims_nothing() -> None:
    session = new_session()
    inbox = HeldInbox(session, WaitingMessages(text="later", files=()))
    failing = runtime_over(SteppedClient([Failed(reason="down")]), inbox=inbox)
    asking = runtime_over(
        SteppedClient(calls_tool("ask", '{"value": "x"}')), pending_tool(), inbox=inbox
    )

    failed = await drain(failing.run("hi", session=session, bot_id="b"))
    waited = await drain(asking.run("again", session=session, bot_id="b"))

    assert isinstance(failed[-1], AgentFailed)
    assert isinstance(waited[-1], AgentPending)
    assert inbox.claimed_after == []


async def test_the_no_op_inbox_holds_nothing_and_is_the_default() -> None:
    assert await NO_INBOX.claim("any") is None
    assert Runtime(models=OneModel(SteppedClient()), images=no_images()).inbox is NO_INBOX


async def test_a_helper_run_to_its_end_has_no_inbox(tmp_path) -> None:
    logs = durable_service(tmp_path / "subagents")
    session = await logs.create("helper")
    inbox = HeldInbox(session, WaitingMessages(text="not for a helper", files=()))
    runtime = runtime_over(SteppedClient(completed("done")), inbox=inbox)

    await run_to_end(runtime, logs, session, HelperTurn(intro="", prompt="go", bot_id="b"))

    assert inbox.claimed_after == []
    assert said(session) == [(0, "go")]
