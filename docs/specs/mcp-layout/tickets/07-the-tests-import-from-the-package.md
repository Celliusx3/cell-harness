# 07 — the tests import from the package

## Status

open

## What to build

1. Every test file that imports a name `harness/mcp/__init__.py` exports imports it from `harness.mcp`.
2. That covers `tests/webapp.py` and the 13 other test files that import `McpService` by path.
3. It also covers the error imports in `test_mcp_service.py`, `test_mcp_tool.py`, `test_web_errors.py` and `test_mcp_errors.py`.
4. A test of a name the package does not export keeps importing its module by path.
5. A test that imports `connection` as a module, to change its timeout, keeps doing so.

## Checks

1. `make test` passes 1669 tests. `make lint` is green.
2. `git grep -n "from harness.mcp.service import"` finds nothing.

## Blocked by

06
