"""The bot is told the chat's mode once it was switched, and at its next step when it changes."""

from __future__ import annotations

from harness.llm import UserMessage
from harness.session.domain.models import ApplicationMessageEvent, ApprovalModeChange
from tests.unit.fakes import SteppedClient, completed, echo_tool
from tests.unit.helpers import drain, new_session, runtime_over

AUTO_LINE = (
    "<system-reminder>\nApproval mode: auto. Your calls run without asking the user."
    "\n</system-reminder>"
)
CHANGED = "The approval mode changed from ask to auto (changed by the user)."


def _runtime(client: SteppedClient):
    return runtime_over(client, echo_tool("a"))


async def test_a_chat_never_switched_is_asked_as_before() -> None:
    client = SteppedClient(completed("hi"))
    session = new_session()

    await drain(_runtime(client).run("hello", session=session, bot_id="b"))

    assert all(AUTO_LINE not in str(message) for message in client.seen)


async def test_a_switched_chat_ends_each_request_with_its_mode() -> None:
    client = SteppedClient(completed("one"), completed("two"))
    runtime = _runtime(client)
    session = new_session()
    await drain(runtime.run("first", session=session, bot_id="b"))
    before = client.seen_per_call[0]

    session.append(ApprovalModeChange(mode="auto"))
    await drain(runtime.run("second", session=session, bot_id="b"))

    after = client.seen_per_call[1]
    assert after[-1] == UserMessage(content=AUTO_LINE)
    assert after[: len(before)] == before


async def test_a_switch_since_the_last_step_is_told_once_at_the_next_step() -> None:
    client = SteppedClient(completed("one"), completed("two"), completed("three"))
    runtime = _runtime(client)
    session = new_session()
    await drain(runtime.run("first", session=session, bot_id="b"))

    session.append(ApprovalModeChange(mode="auto"))
    await drain(runtime.run("second", session=session, bot_id="b"))
    await drain(runtime.run("third", session=session, bot_id="b"))

    told = [e for e in session.events() if isinstance(e, ApplicationMessageEvent)]
    assert [e.message.content for e in told] == [CHANGED]
    assert UserMessage(content=CHANGED) in client.seen_per_call[1]


async def test_switching_away_and_back_before_the_next_step_tells_nothing() -> None:
    client = SteppedClient(completed("one"), completed("two"))
    runtime = _runtime(client)
    session = new_session()
    await drain(runtime.run("first", session=session, bot_id="b"))

    session.append(ApprovalModeChange(mode="auto"))
    session.append(ApprovalModeChange(mode="ask"))
    await drain(runtime.run("second", session=session, bot_id="b"))

    assert not [e for e in session.events() if isinstance(e, ApplicationMessageEvent)]


async def test_a_switch_before_the_first_step_tells_nothing_but_the_mode() -> None:
    client = SteppedClient(completed("one"))
    session = new_session()
    session.append(ApprovalModeChange(mode="auto"))

    await drain(_runtime(client).run("first", session=session, bot_id="b"))

    assert not [e for e in session.events() if isinstance(e, ApplicationMessageEvent)]
    assert client.seen[-1] == UserMessage(content=AUTO_LINE)
