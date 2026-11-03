# 10 — the files only the package uses are private

## Status

open

## What to build

1. Rename `harness/mcp/connection.py` to `_connection.py`. The package exports none of its names.
2. Rename `harness/mcp/result.py` to `_result.py`, for the same reason.
3. Update `service.py` and `tool.py`, which import them.
4. Update the tests that import them by path.
5. Those are `test_mcp_service.py`, `test_mcp_stdio.py`, `test_mcp_errors.py`, `test_mcp_tool.py`, `test_mcp_images.py` and `test_tool_files.py`.
6. Fix the paths that name the two files in `mcp-servers/README.md`, `docs/prompt-failures.md` and `PHASES.md`.

## Checks

1. `make test` passes 1669 tests. `make lint` is green.
2. Import `harness.mcp._connection` from `web/server.py` on purpose. The private-module test in `test_layering.py` fails. Undo it.
3. `git grep -nwE "mcp/(connection|result)\.py|harness\.mcp\.(connection|result)"` finds nothing.

## Blocked by

09
