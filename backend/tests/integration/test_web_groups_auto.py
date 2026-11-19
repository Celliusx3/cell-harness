"""A group on Auto over HTTP: one call to its model picks who answers a message naming nobody."""

from __future__ import annotations

import asyncio
import json

import pytest

from harness.groups import GroupEdit
from harness.runs.service import discussion
from tests.integration.test_web_groups import _group, _send
from tests.unit.fakes import completed
from tests.webapp import MODEL_CREDENTIAL


def _pick(name: str, confidence: float) -> list:
    return completed(json.dumps({"pick": name, "confidence": confidence}))


async def _on_auto(tmp_path, *scripts, lead: str = "researcher"):
    client, model, runs, chat, researcher, writer = await _group(tmp_path, *scripts)
    edit = GroupEdit(
        name="Market Desk",
        member_ids=(researcher, writer),
        lead_id={"researcher": researcher, "writer": writer}[lead],
        reply="auto",
        auto_model=MODEL_CREDENTIAL,
    )
    runs.groups.update(chat, edit)
    return client, model, runs, chat, researcher, writer


def _speakers(events: list[dict]) -> list[str]:
    return [e["bot_id"] for e in events if e["type"] == "turn/start"]


async def test_a_sure_pick_answers_alone_and_the_pick_is_logged(tmp_path) -> None:
    client, model, runs, chat, _, writer = await _on_auto(
        tmp_path, _pick("Writer", 0.94), completed("NVDA is at 120.")
    )
    async with client:
        events = await _send(client, runs, chat, "what is NVDA's price?")

    picks = [e for e in events if e["type"] == "group/auto_pick"]
    assert picks == [
        {
            "type": "group/auto_pick",
            "turn": 0,
            "bot_id": writer,
            "confidence": 0.94,
            "fallback": False,
        }
    ]
    assert _speakers(events) == [writer]
    assert model.calls == 2


async def test_everyone_picked_surely_queues_every_member(tmp_path) -> None:
    client, _, runs, chat, researcher, writer = await _on_auto(
        tmp_path, _pick("everyone", 0.9), completed("Mine."), completed("Mine too.")
    )
    async with client:
        events = await _send(client, runs, chat, "each of you, your view?")

    assert _speakers(events) == [researcher, writer]


@pytest.mark.parametrize("answer", [_pick("Researcher", 0.4), completed("Researcher, maybe.")])
async def test_an_unsure_or_broken_pick_goes_to_the_lead(tmp_path, answer) -> None:
    client, _, runs, chat, _, writer = await _on_auto(
        tmp_path, answer, completed("Lead here."), lead="writer"
    )
    async with client:
        events = await _send(client, runs, chat, "what now?")

    pick = next(e for e in events if e["type"] == "group/auto_pick")
    assert (pick["bot_id"], pick["fallback"]) == (writer, True)
    assert _speakers(events) == [writer]


async def test_a_named_bot_answers_without_asking_the_model(tmp_path) -> None:
    client, model, runs, chat, _, writer = await _on_auto(tmp_path, completed("Writer here."))
    async with client:
        events = await _send(client, runs, chat, "@Writer, a post?")

    assert not any(e["type"] == "group/auto_pick" for e in events)
    assert _speakers(events) == [writer]
    assert model.calls == 1


async def test_auto_with_a_model_is_saved_and_listed(tmp_path) -> None:
    client, _, _, chat, researcher, writer = await _group(tmp_path, completed("hi"))
    edit = {
        "name": "Desk",
        "member_ids": [researcher, writer],
        "lead_id": None,
        "reply": "auto",
        "auto_model": MODEL_CREDENTIAL,
    }
    async with client:
        patched = await client.patch(f"/api/groups/{chat}", json=edit)
        listed = (await client.get("/api/groups")).json()

    assert patched.status_code == 200, patched.text
    assert listed == [{"id": chat, **edit}]


async def test_auto_without_a_model_is_refused(tmp_path) -> None:
    client, _, _, chat, researcher, writer = await _group(tmp_path, completed("hi"))
    edit = {"name": "Desk", "member_ids": [researcher, writer], "lead_id": None, "reply": "auto"}
    async with client:
        patched = await client.patch(f"/api/groups/{chat}", json=edit)

    assert patched.status_code == 422


async def test_stopping_while_auto_picks_keeps_the_message(tmp_path, monkeypatch) -> None:
    async def never_picks(*_args) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(discussion, "auto_pick", never_picks)
    client, model, runs, chat, _, _ = await _on_auto(tmp_path, completed("hi"))
    async with client:
        sent = await client.post(
            f"/api/conversations/{chat}/messages", json={"prompt": "what now?"}
        )
        assert sent.status_code == 202
        await asyncio.sleep(0.05)
        assert await runs.stop(chat)
        events = (await client.get(f"/api/conversations/{chat}")).json()["events"]

    assert [e["message"]["content"] for e in events if e["type"] == "user/message"] == ["what now?"]
    assert model.calls == 0
