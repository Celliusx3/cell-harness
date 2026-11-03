# 09 — the shapes are a models folder

## Status

open

## What to build

1. Create `harness/mcp/models/` with a one-line `__init__.py`, as `tools/models/` has.
2. `models/errors.py` gets the three error classes. Delete `harness/mcp/errors.py`.
3. `models/status.py` gets `Status` and `ServerStatus` from `connection.py`.
4. `models/commands.py` gets `_Call`, `_Read` and `_Command`, as `ToolCallCommand`, `ResourceReadCommand` and `Command`.
5. `models/returned_file.py` gets `ReturnedFile` and `FILES_META` from `result.py`.
6. `describe_error` moves into `connection.py`, its one caller.
7. Update the imports in `mcp/__init__.py`, `connection.py`, `service.py`, `tool.py` and `result.py`.
8. Update `test_mcp_errors.py` and `test_tool_files.py`, which import names the package does not export.

## Checks

1. `make test` passes 1669 tests. `make lint` is green.
2. The 6 error tests, 18 service tests and 9 returned-file tests pass with the same names.
3. `git grep -nwE "harness.mcp.errors|_Call|_Read|_Command" backend` finds nothing.

## Blocked by

08
