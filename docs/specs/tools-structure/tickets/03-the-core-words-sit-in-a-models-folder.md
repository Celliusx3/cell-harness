# 03 · The core words sit in a models folder, one file per subject

**Status.** open

**What to build.** `backend/harness/tools/models/`:
- `__init__.py`: a one-line docstring only.
- `outcome.py`: `INVALID_ARGUMENTS`, `UNKNOWN_TOOL`, `EXECUTION_ERROR`, `REFUSED`, `BLOCKED`, `ToolUi`, `ReturnedImage`, `Ok`, `Failure`, `Pending`, `ToolOutcome`, `render_outcome`, moved from `definition.py`.
- `context.py`: `ToolProgressReporter` from `progress.py`, and `CallOrigin`, `ToolContext` from `context.py`. `tools/progress.py` and `tools/context.py` are deleted.
- `decision.py`: `DENIED`, `Scope`, `Approved`, `Denied`, `Decision`, `_DECISION`, `parse_decision`, moved from `approval.py`.

Each name moves unchanged, with its docstring. `definition.py` keeps `NAMESPACE` and `ToolDefinition`; `approval.py` keeps `StandingGrants` and `ApprovalGate`. Every import inside `backend/harness/tools/` follows (the door, `registry`, `dispatcher`, `pipeline`, `client/`, `native/`), and so do the tests that import `DENIED`, `Denied` or `ToolProgressReporter` by path. The tools line of the layout in `CLAUDE.md` follows.

**Checks.** `make lint` and `make test` green (1488 passed). `git grep -nE "harness\.tools\.(context|progress)\b|tools/(context|progress)\.py" -- . ':!docs/specs'` finds nothing. Break: change `Approved`'s `kind` literal to `"approve"`; the approval tests fail.

**Blocked by.** 02
