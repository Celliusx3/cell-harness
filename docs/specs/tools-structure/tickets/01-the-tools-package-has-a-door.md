# 01 · The tools package has a door, and the app uses it

**Status.** open

**What to build.**
- First, in `backend/tests/unit/test_layering.py`, a test that imports `harness.session.models`, `harness.tools.client` and `harness.skills.tool` each first, on its own, in a fresh interpreter. It passes on the code as it is.
- `backend/harness/tools/__init__.py` exports, with `__all__`, exactly the names other packages import today: from `definition`, `BLOCKED`, `EXECUTION_ERROR`, `Failure`, `INVALID_ARGUMENTS`, `NAMESPACE`, `Ok`, `Pending`, `REFUSED`, `ReturnedImage`, `ToolDefinition`, `ToolOutcome`, `ToolUi`, `UNKNOWN_TOOL`, `render_outcome`; from `context`, `CallOrigin`, `ToolContext`; from `approval`, `ApprovalGate`, `Approved`; `ToolDispatcher`, `ToolPipeline`, `ToolRegistry`. It imports nothing from `client/` or `native/`.
- Every file under `backend/harness/` outside `tools/` that imports from `harness.tools.definition`, `.context`, `.progress`, `.approval`, `.registry`, `.dispatcher` or `.pipeline` imports from `harness.tools` instead (21 files). Files inside `tools/` keep importing each other directly; the client and native doors are unchanged.

**Checks.** `make lint` and `make test` green (1485 passed, plus the new test). `git grep -nE "from harness\.tools\.(definition|context|progress|approval|registry|dispatcher|pipeline) import" -- backend/harness ':!backend/harness/tools'` finds nothing. Break: add `from harness.tools.client import PendingCall` to the door; the new test fails for `harness.session.models`.

**Blocked by.** none
