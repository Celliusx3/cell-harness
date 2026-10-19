# 02 · The approval gate is the approvals

**Status.** open

**What to build.** `tools/approval.py` becomes `tools/approvals.py`, and `ApprovalGate` becomes `Approvals`. Its `tools` property and the client service's and channels' `gated_tools` become `tools_that_ask`. Every variable, parameter and attribute that holds it (`gate`, `_gate`) becomes `approvals` or `_approvals`, and the test helper `no_gate` becomes `no_approvals`; the files where `gate` names a test tool or an event keep it. The Approvals route's response model, also called `Approvals`, becomes `GrantedTools`, with the same JSON.

**Checks.** `make lint` and `make test` green (1489 passed). `git grep -nwE "ApprovalGate|no_gate|gated_tools|harness\.tools\.approval" -- backend` finds nothing.

**Blocked by.** 01
