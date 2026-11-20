"""Auto: one call to the group's model picks who answers, and anything short of sure is the lead."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from harness.groups import Group
from harness.llm import AssistantMessage, LLMClient, Message, StreamEvent, ToolSpec, UserMessage
from harness.runs.service import auto_pick as auto_pick_module
from harness.runs.service.auto_pick import auto_pick
from harness.runtime.models import NoModel
from harness.session.domain.models import (
    AssistantMessageEvent,
    GroupAutoPickEvent,
    TurnStart,
    UserMessageEvent,
)
from tests.unit.fakes import HangingClient, OneModel, ScriptedClient, completed
from tests.unit.helpers import durable_service
from tests.unit.test_speaker_queue import TEAM, R, W

DESK = Group(
    id="g", name="Desk", member_ids=("r", "w", "e"), lead_id="w", reply="auto", auto_model="m"
)


class RaisingClient(LLMClient):
    """Raises on every call."""

    async def stream_completion(
        self, messages: list[Message], *, tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        raise RuntimeError("the endpoint is down")
        yield


class NoModels:
    """No credential is saved by any name."""

    async def model_for(self, bot_id: str | None) -> NoModel:
        return NoModel()

    async def model_named(self, name: str) -> NoModel:
        return NoModel()


async def _pick(tmp_path, client: LLMClient, text: str = "what is NVDA's price?"):
    session = await durable_service(tmp_path).create()
    return await auto_pick(OneModel(client), session, DESK, TEAM, text)


async def test_a_sure_pick_names_that_member(tmp_path) -> None:
    picked = await _pick(
        tmp_path, ScriptedClient(completed('{"pick": "Researcher", "confidence": 0.94}'))
    )

    assert picked == GroupAutoPickEvent(turn=0, bot_id=R.id, confidence=0.94, fallback=False)


async def test_everyone_picked_surely_is_no_one_member(tmp_path) -> None:
    answer = '```json\n{"pick": "everyone", "confidence": 0.9}\n```'
    picked = await _pick(tmp_path, ScriptedClient(completed(answer)))

    assert picked == GroupAutoPickEvent(turn=0, bot_id=None, confidence=0.9, fallback=False)


async def test_an_unsure_pick_goes_to_the_lead(tmp_path) -> None:
    picked = await _pick(
        tmp_path, ScriptedClient(completed('{"pick": "Researcher", "confidence": 0.4}'))
    )

    assert picked == GroupAutoPickEvent(turn=0, bot_id=W.id, confidence=0.4, fallback=True)


@pytest.mark.parametrize(
    "client",
    [
        ScriptedClient(completed("Researcher, I think.")),
        ScriptedClient(completed('{"pick": "Nobody Here", "confidence": 0.99}')),
        ScriptedClient(completed('{"pick": "Researcher", "confidence": 7}')),
        ScriptedClient([]),
        RaisingClient(),
    ],
)
async def test_a_broken_answer_or_a_failed_call_goes_to_the_lead(tmp_path, client) -> None:
    picked = await _pick(tmp_path, client)

    assert (picked.bot_id, picked.fallback) == (W.id, True)


async def test_a_call_that_hangs_goes_to_the_lead(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auto_pick_module, "AUTO_PICK_TIMEOUT_SECONDS", 0.01)

    picked = await _pick(tmp_path, HangingClient('{"pick"'))

    assert (picked.bot_id, picked.fallback) == (W.id, True)


async def test_no_saved_model_goes_to_the_lead(tmp_path) -> None:
    session = await durable_service(tmp_path).create()

    picked = await auto_pick(NoModels(), session, DESK, TEAM, "hi")

    assert (picked.bot_id, picked.confidence, picked.fallback) == (W.id, 0.0, True)


async def test_the_model_is_shown_the_group_its_members_recent_lines_and_the_message(
    tmp_path,
) -> None:
    client = ScriptedClient(completed('{"pick": "Writer", "confidence": 0.8}'))
    session = await durable_service(tmp_path).create()
    session.append(TurnStart(turn=0, bot_id=R.id))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="find sources")))
    session.append(
        AssistantMessageEvent(turn=0, step=0, message=AssistantMessage(content="Three sources."))
    )

    picked = await auto_pick(OneModel(client), session, DESK, TEAM, "now write it up")

    asked = client.seen[0].content
    assert picked.turn == 1
    for shown in ("Desk", "Researcher: Cite.", "Copy Editor: Edit.", "now write it up"):
        assert shown in asked
    assert asked.index("person: find sources") < asked.index("Researcher: Three sources.")
