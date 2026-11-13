# 14. Layer tools: service and router

**Status.** open

## What to build

Move the code that acts and the routes of `tools`. Update `CIRCULAR_IMPORT_RISK` in `test_layering.py` if a path in it moves.
- `tools/service.py` to `tools/service/tool_service.py`
- `tools/toolset.py` to `tools/service/toolset.py`
- `tools/approvals.py` to `tools/service/approval_service.py`
- `tools/approvals_router.py` to `tools/router/approval_router.py`
- `tools/approvals_schemas.py` to `tools/router/approval_schemas.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

13
