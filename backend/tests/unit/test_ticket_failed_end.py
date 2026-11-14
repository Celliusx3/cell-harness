"""A worker's turn that fails tells the bot why, in the words the failure came with."""

from __future__ import annotations

from harness.runtime.events import AgentFailed
from harness.tickets.domain.prompts import TICKET_DID_NOT_FINISH
from harness.tickets.service.worker import worker_end

RATE_LIMITED = "provider returned 429: qwen/qwen3.8-27b is temporarily rate-limited upstream"


def test_a_failed_turn_s_report_carries_its_reason() -> None:
    end = worker_end(AgentFailed(reason=RATE_LIMITED), None)

    assert end.state == "failed"
    assert RATE_LIMITED in end.text


def test_a_turn_that_ended_with_no_event_still_says_it_did_not_finish() -> None:
    end = worker_end(None, None)

    assert end.state == "failed"
    assert end.text == TICKET_DID_NOT_FINISH
