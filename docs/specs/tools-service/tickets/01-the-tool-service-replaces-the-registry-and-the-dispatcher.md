# 01 · The tool service replaces the registry and the dispatcher

**Status.** open

**What to build.**
- First, in `backend/tests/unit/test_dispatcher.py`, a test that a call to a listed tool waits (`Pending`) before its name is looked up, even when no tool by that name is registered. It passes on the code as it is.
- `backend/harness/tools/service.py`: `Disposer`, `ToolProvider`, `DuplicateToolError` from `registry.py`, and `ToolService(tools, *, gate, providers=())` with `register`, `add_provider`, `all`, `get` from `ToolRegistry` and `dispatch`, `_unknown_tool_message` from `ToolDispatcher`, each body unchanged. `registry.py` and `dispatcher.py` are deleted.
- `ToolPipeline(tool_service, default_tools)` with the public attribute `tool_service`; `code_mode_tools(*, tool_service, runner, withheld)`; in `web/runtime.py`, `_register_code_mode(tool_service, settings)`, `_register_run_subagent(tool_service, runtime, logs)` and `attach_bot_messages(tool_service, sessions, bots, runs)`; `web/server.py` passes `runtime.tools.tool_service`.
- The door exports `ToolService` in place of `ToolDispatcher` and `ToolRegistry`. The 11 test files that build a registry or a dispatcher build a `ToolService`, and import `ToolProvider` and `DuplicateToolError` from `harness.tools.service`.

**Checks.** `make lint` and `make test` green (1489 passed). Every tool's schema is byte-identical. `git grep -nE "ToolRegistry|ToolDispatcher|harness\.tools\.(registry|dispatcher)" -- backend` finds nothing. Break: make `dispatch` look the tool up before asking the gate; the new test fails. Break: drop the duplicate check from `register`; `test_duplicate_static_registration_fails_loudly` fails.

**Blocked by.** none
