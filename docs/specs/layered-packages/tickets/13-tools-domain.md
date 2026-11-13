# 13. Layer tools: domain

**Status.** done

## What to build

Move the tool data of `tools`. Delete the empty `models/` folder. `client/` and `native/` keep their shape.
- `tools/models/context.py` to `tools/domain/context.py`
- `tools/models/decision.py` to `tools/domain/decision.py`
- `tools/models/outcome.py` to `tools/domain/outcome.py`
- `tools/models/tool.py` to `tools/domain/tool.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

01
