# 01 — the group flattening is tested

## Status

open

## What to build

1. Write tests/unit/test_mcp_errors.py for the promise of the error describer
   in harness/mcp/errors.py.
2. One test: a one-member exception group comes back as that member's message.
3. One test: an error whose message is empty comes back as its type name.
4. No rename yet. The test passes on the code as it stands.

## Checks

1. `cd backend && uv run pytest tests/unit/test_mcp_errors.py --no-cov` passes
   before and after every later ticket.
2. Break one unwrap line on purpose. The test fails. Undo the break.

## Blocked by

none
