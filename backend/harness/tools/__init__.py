"""Tools the model can call — phase 2.

Its own subpackage rather than living under `agent/`, because it imports nothing
from there and nearly everything will import it: MCP (phase 5), skills (phase 6),
and the control plane each build tools without being about agents.

- `definition` — what a tool *is*: a schema the model is told, a parser, and an
  executor. `ToolDefinition.spec()` is the allowlist that keeps everything else
  off the wire.
- `registry` — the set an agent can call, resolved live so a source that
  connects mid-conversation is usable on the next turn.
- `pipeline` — guarded execution: one interceptable waterfall around the call.
- `progress` — how a running tool reports partway.
"""

from harness.tools.definition import (
    Failure,
    Ok,
    ToolDefinition,
    ToolOutcome,
    render_outcome,
)
from harness.tools.progress import ToolProgressReporter
from harness.tools.registry import ToolProvider, ToolRegistry

__all__ = [
    "Failure",
    "Ok",
    "ToolDefinition",
    "ToolOutcome",
    "ToolProgressReporter",
    "ToolProvider",
    "ToolRegistry",
    "render_outcome",
]
