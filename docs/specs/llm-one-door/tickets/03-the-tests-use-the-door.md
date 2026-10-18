# 03 · The tests use the door

**Status.** done

**What to build.** Every file under `backend/tests/` that imports from `harness.llm.messages`, `harness.llm.stream`, `harness.llm.client`, `harness.llm.adapters.openai` or `harness.llm.adapters.context_window` by name imports from `harness.llm` or `harness.llm.adapters` instead (76 files). A test that imports a module object to replace its `httpx` (`from harness.llm.adapters import openai as adapter_module`) keeps doing so; a test of a private file keeps importing it.

**Checks.** `make lint` and `make test` green (1455 passed). `git grep -nE "from harness\.llm\.(messages|stream|client|adapters\.openai|adapters\.context_window) import" -- backend ':!backend/harness/llm'` finds nothing.

**Blocked by.** 02
