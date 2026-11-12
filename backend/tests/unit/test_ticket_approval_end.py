"""A worker's turn that waits on an approval ends as a question the person answers in the app."""

from __future__ import annotations

from harness.runtime.events import AgentPending
from harness.tickets.worker import WorkerEnd, worker_end


def test_an_approval_pending_end_becomes_a_blocked_approval_report() -> None:
    end = worker_end(AgentPending(tool_call_id="f1", name="fetch_with_secret"), None)

    assert end == WorkerEnd(
        state="blocked",
        text="The worker waits for the user to allow fetch_with_secret.",
        question="Allow fetch_with_secret?",
        ask="approval",
        approval_call_id="f1",
        approval_tool="fetch_with_secret",
    )
