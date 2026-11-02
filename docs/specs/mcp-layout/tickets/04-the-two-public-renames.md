# 04 — the two public renames

## Status

open

## What to build

1. Rename the app-visibility check in harness/mcp/tool.py so its name starts
   with is. Update harness/web/routes/mcp.py and test_mcp_tool.py.
2. Rename the error describer in harness/mcp/errors.py so the import names its
   object. Update its two uses in harness/mcp/connection.py and the import in
   test_mcp_errors.py.

## Checks

1. `cd backend && make test-unit && make test-integration` is green before and
   after.
2. `make lint` is green after.
3. test_web_errors still maps the three mcp errors to their statuses.

## Blocked by

03
