"""Client tools — tools the *client* answers, not the server.

The server does not know where the person is, what is on their clipboard, or
what their calendar says; their device does. A client tool is a **declaration**
(`ClientTool`): a name, a description, what the model passes, and what a
shared answer carries. Everything else is this package's, the same for every
datum — the tool says `Pending` and the loop ends the turn there; which call
may be answered is read off the log (`pending_call`); a posted body is
validated against that tool (`ClientTools.parse`); and the ways an answer can
go — shared, declined, unavailable, or skipped because the person moved on —
are one vocabulary the model learns once. `ClientToolService` is the one
object the agent, the chats and the route hold, so those checks are written
once; the answer it accepts opens the next turn (`RunStore.resume`).

The request the client sees is the ordinary `tool/call` already in the log and
on the stream; the answer is the ordinary `tool/result`, the first event of
the turn that carries it. Nothing waits in memory: a reload, a restart, a week
— the log holds the pending call until the person answers it or walks past it.
A new datum is one declaration here and one handler in the browser — nothing
in this package changes. Lineage and the alternatives not taken:
[docs/client-data.md](../../../../docs/client-data.md).
"""

from harness.tools.client.catalog import (
    DECLINED,
    UNAVAILABLE,
    ClientOutput,
    ClientTool,
    ClientTools,
    Declined,
    Shared,
    Unavailable,
)
from harness.tools.client.pending import PendingCall, pending_call
from harness.tools.client.service import Accepted, ClientToolService, Refused

__all__ = [
    "Accepted",
    "DECLINED",
    "UNAVAILABLE",
    "ClientToolService",
    "ClientOutput",
    "ClientTool",
    "ClientTools",
    "Declined",
    "PendingCall",
    "Refused",
    "Shared",
    "Unavailable",
    "pending_call",
]
