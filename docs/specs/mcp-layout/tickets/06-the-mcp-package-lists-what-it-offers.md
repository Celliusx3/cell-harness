# 06 — the mcp package lists what it offers

## Status

done

## What to build

1. Make `harness/mcp/__init__.py` export, with `__all__`, the names the app and its tests import today.
2. From `service`, that is `McpService`. From `errors`, `McpConnectionError`, `McpNotConnectedError` and `McpTimeoutError`.
3. From `tool`, that is `is_app_visible` and `ui_resource_uri`. From `client`, `ClientFactory` and `open_client`.
4. Import those names from `harness.mcp` in `web/errors.py`, `web/routes/mcp.py`, `web/runtime.py` and `web/server.py`.
5. Files inside `harness/mcp/` keep importing each other by path.

## Checks

1. `make test` passes 1669 tests. `make lint` is green.
2. `git grep -nE "from harness\.mcp\.[a-z_]+ import" -- backend/harness ':!backend/harness/mcp'` finds nothing.

## Blocked by

05
