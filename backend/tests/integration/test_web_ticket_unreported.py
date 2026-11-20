"""A worker that ends its turn without `ticket_report` is reminded once, then its ticket fails."""

from __future__ import annotations

import json

from harness.bots import ASSISTANT_ID
from harness.tools.native.tickets import TICKET_REPORT, TICKET_ROUTE
from tests.integration.ticket_helpers import WORKER_START, ticketing_app
from tests.integration.web_helpers import ASSISTANT_START, of_type, once_said, send
from tests.unit.fakes import calls_tool, completed

ACCEPTED = json.dumps(
    {"items": [{"kind": "accept", "title": "Translate the chapter", "task": "Translate it."}]}
)
TOOL_CALL_AS_TEXT = "<|tool_call>call:computer__shell{command:detect}"
READY = json.dumps({"state": "ready", "summary": "Translated 12 pages."})


def _bot_script(last: str) -> list:
    return [calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"), completed("On it."), completed(last)]


async def test_a_worker_reminded_to_report_ends_its_ticket_with_that_report(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [
                completed("Done, I think."),
                calls_tool(TICKET_REPORT, READY, id="r1"),
            ],
            ASSISTANT_START: _bot_script("Here is the chapter."),
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "translate this chapter")
        log = await once_said(client, ASSISTANT_ID, "Here is the chapter.")

    (ticket,) = world.tickets.of_bot(ASSISTANT_ID)
    assert ticket.state == "done"
    (report,) = of_type(log, "ticket/report")
    assert report["report"]["text"] == "Translated 12 pages."


async def test_a_worker_that_never_reports_ends_its_ticket_as_failed(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [completed(TOOL_CALL_AS_TEXT)],
            ASSISTANT_START: _bot_script("The worker did not finish."),
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "translate this chapter")
        log = await once_said(client, ASSISTANT_ID, "The worker did not finish.")

    (ticket,) = world.tickets.of_bot(ASSISTANT_ID)
    assert ticket.state == "failed"
    assert len(world.model.seen_by[WORKER_START]) == 2
    (report,) = of_type(log, "ticket/report")
    assert TOOL_CALL_AS_TEXT in report["report"]["text"]
