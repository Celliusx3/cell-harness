# 04 · The names say what they return

**Status.** open

**What to build.** Each rename moves every caller, test and doc with it, and deletes the old name:
- `render_outcome` → `blocks_of` (`models/outcome.py`, the door, `runtime/tool_run.py`, `native/code/tools.py`).
- `ToolPipeline.approve` → `execute_approved` (`runtime/tool_run.py`).
- `ApprovalGate.asks` → `should_ask` (`dispatcher.py`); `ApprovalGate.granted` → `granted_tools` (`approval.py`, `web/routes/approvals.py`).
- `pending_tool_calls` → `still_pending` (`client/pending.py`, the client door, `channels/replies.py`).
- Private helpers: `ToolDefinition._missing_required` → `_missing_required_message`, `ToolDispatcher._unknown` → `_unknown_tool_message`, `ToolPipeline._offered` → `_offered_tools`, `pipeline._not_offered` → `_not_offered_message`, `ApprovalGate._write` → `_write_grants`.

**Checks.** `make lint` and `make test` green (1488 passed). `git grep -nwE "render_outcome|pending_tool_calls|_missing_required|_unknown|_offered|_not_offered" -- . ':!docs/specs'` finds nothing, nor does a search for `\.approve(`, `\.asks(`, `\.granted(` and `\._write(` in `backend/`. Break: make `should_ask` return `False`; the approval tests fail.

**Blocked by.** 03
