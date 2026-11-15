# 02 "Allow for this conversation" reaches the chat's workers

**Status.** done

**What to build.** In cell-harness. A worker runs a tool unasked when its own log or its chat's log holds a grant for it. The logs are read at the time of the call. 

A "for this conversation" answer on a worker's approval card is recorded in the chat's log, so it covers every worker of that chat. The data shape stays `ApprovalGrant`. Files: `backend/harness/runtime/service.py`, `backend/harness/tools/service/toolset.py`, `backend/harness/tickets/service/worker.py`, and their tests.

**Checks.** An integration test starts two tickets in one chat in Ask mode. The first asks for `computer__shell`. It is answered "for this conversation" on the first ticket's card, and the second ticket then runs `computer__shell` without asking. 

A grant made in the chat itself before a ticket starts also reaches that ticket. A grant in another chat reaches neither. `make lint` and `make test` are green, coverage 80% or more.

**Blocked by.** none
