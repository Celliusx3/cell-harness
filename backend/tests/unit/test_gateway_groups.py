"""The gateway in a group's chat: a queued message once nobody is left to answer it."""

from __future__ import annotations

import asyncio
import logging

from harness.bots import BotDraft, BotService, GroupDraft
from harness.channels.protocol import InboundMessage
from tests.unit.fakes import SteppedClient, calls_tool, hanging_tool
from tests.unit.helpers import durable_service, no_skills, run_service
from tests.webapp import web_gateway


async def test_a_queued_message_for_a_group_with_nobody_left_is_dropped_with_a_warning(
    tmp_path, caplog
) -> None:
    service = durable_service(tmp_path / "sessions")
    bots = BotService(tmp_path / "bots.json", service, assistant_instructions="Be kind.")
    runs = run_service(
        service, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), bots=bots
    )
    gateway, _ = web_gateway(tmp_path, service, runs, skills=no_skills(), bots=bots)
    researcher = await bots.create(BotDraft(name="Researcher", instructions="Cite."))
    writer = await bots.create(BotDraft(name="Writer", instructions="Post."))
    group = await bots.create_group(
        GroupDraft(name="Launch", member_ids=(researcher.id, writer.id))
    )
    await gateway.receive(InboundMessage(channel="web", chat_id=group.id, text="go"))
    await gateway.receive(InboundMessage(channel="web", chat_id=group.id, text="and then?"))

    bots.archive(writer.id)
    bots.archive(researcher.id)
    with caplog.at_level(logging.WARNING, logger="harness.channels"):
        await runs.stop(group.id)
        for _ in range(200):
            if not gateway._tasks.running():
                break
            await asyncio.sleep(0.01)

    assert runs.active(group.id) is None
    assert "nobody" in caplog.text
