# 02 · The tests use the door

**Status.** open

**What to build.** Every file under `backend/tests/` that imports a name the door exports from `harness.tools.definition`, `.context`, `.approval`, `.registry`, `.dispatcher` or `.pipeline` imports it from `harness.tools` instead (58 files). A name the door does not export keeps its own file: `DENIED` and `Denied` from `approval`, `MAX_TOOLS_SELECTED` from `pipeline`, `ToolProgressReporter` from `progress`, `DuplicateToolError` and `ToolProvider` from `registry`. The test that imports `ToolSpec` through `harness.tools.definition` imports it from `harness.llm`.

**Checks.** `make lint` and `make test` green (1486 passed). `git grep -nE "from harness\.tools\.(definition|context|dispatcher) import" -- backend/tests` finds nothing, and every remaining by-path import of `approval`, `pipeline`, `progress` or `registry` names only the six names above.

**Blocked by.** 01
