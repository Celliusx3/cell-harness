"""What a tool is handed about the call it is running.

`call_id` is the model's identifier for this invocation — the thing a
`tool/result` is matched to. Most tools never read it. The one that must is a
tool whose answer comes from *outside* the process: it parks on the id and
someone else — a browser, a chat app — resolves it by that id later. Without
this, such a tool could not tell which call it was, and an answer arriving over
HTTP would have nothing to be matched against.

`progress` is the per-call channel back to the loop, unchanged from when it was
passed alone. Both are per call, both are created by the dispatcher from the
`ToolCall` it holds, so bundling them costs nothing and keeps `execute` at two
arguments.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness.tools.progress import ToolProgressReporter


@dataclass(frozen=True)
class ToolContext:
    """Per-call facts, read-only, given to every `execute`."""

    call_id: str
    progress: ToolProgressReporter
