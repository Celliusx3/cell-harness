"""A connected server's instructions reach the system prompt, logged as `server/instructions`."""

from __future__ import annotations

import asyncio
import dataclasses

from harness.mcp import McpService
from harness.runtime.service import Runtime
from harness.session.log import Session
from harness.session.models import ServerInstructionsEvent
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import drain, new_session, runtime_over
from tests.unit.mcp_fakes import FakeFactory, no_keys, servers

PC = "You have a PC."


async def connected(factory: FakeFactory, *ids: str) -> McpService:
    """A started service, waited until its connections have settled."""
    store = McpService(servers(*ids), client_factory=factory, keys=no_keys())
    await store.start()
    for _ in range(200):
        if all(s.status != "connecting" for s in store.statuses()):
            return store
        await asyncio.sleep(0.01)
    raise AssertionError("never left `connecting`")


def logged(session: Session) -> list[ServerInstructionsEvent]:
    return [e for e in session.events() if isinstance(e, ServerInstructionsEvent)]


def runtime_with(client: ScriptedClient, store: McpService) -> Runtime:
    return dataclasses.replace(
        runtime_over(client, guidance="GUIDE"), server_instructions=store.instructions
    )


async def test_a_connected_server_s_instructions_are_kept_by_server_id() -> None:
    factory = FakeFactory()
    factory.client.instructions = PC
    store = await connected(factory, "computer")

    assert store.instructions() == {"computer": PC}
    await store.aclose()
    assert store.instructions() == {}


async def test_a_server_with_no_instructions_is_left_out() -> None:
    store = await connected(FakeFactory(), "fs")

    assert store.instructions() == {}
    await store.aclose()


async def test_a_turn_logs_the_instructions_once_and_an_unchanged_turn_logs_none() -> None:
    factory = FakeFactory()
    factory.client.instructions = PC
    store = await connected(factory, "computer")
    runtime = runtime_with(ScriptedClient(completed("ok")), store)
    session = new_session()

    await drain(runtime.run("hi", session=session, bot_id="s"))
    assert logged(session) == [ServerInstructionsEvent(server="computer", instructions=PC)]

    await drain(runtime.run("again", session=session, bot_id="s"))
    assert len(logged(session)) == 1
    await store.aclose()


async def test_the_request_s_system_message_carries_the_instructions() -> None:
    factory = FakeFactory()
    factory.client.instructions = PC
    store = await connected(factory, "computer")
    client = ScriptedClient(completed("ok"))
    session = new_session()

    await drain(runtime_with(client, store).run("hi", session=session, bot_id="s"))

    assert client.seen[0].content == f"GUIDE\n\n{PC}"
    await store.aclose()


async def test_instructions_that_went_away_are_logged_empty_and_leave_the_prompt() -> None:
    factory = FakeFactory()
    factory.client.instructions = PC
    store = await connected(factory, "computer")
    client = ScriptedClient(completed("ok"))
    runtime = runtime_with(client, store)
    session = new_session()
    await drain(runtime.run("hi", session=session, bot_id="s"))

    await store.aclose()
    await drain(runtime.run("again", session=session, bot_id="s"))

    assert logged(session)[-1] == ServerInstructionsEvent(server="computer", instructions="")
    assert client.seen[0].content == "GUIDE"


def test_the_prompt_holds_each_server_s_latest_instructions_as_a_paragraph() -> None:
    runtime = runtime_over(ScriptedClient(completed("x")), guidance="GUIDE")
    session = new_session()
    for event in (
        ServerInstructionsEvent(server="computer", instructions="old"),
        ServerInstructionsEvent(server="places", instructions="Find places."),
        ServerInstructionsEvent(server="computer", instructions=PC),
    ):
        session.append(event)

    system = runtime.request_messages(session)[0]

    assert system.content == f"GUIDE\n\n{PC}\n\nFind places."
