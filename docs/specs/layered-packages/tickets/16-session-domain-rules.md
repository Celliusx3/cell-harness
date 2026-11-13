# 16. Layer session: domain rules

**Status.** open

## What to build

Move the pure rules of `session` that read the log.
- `session/log.py` to `session/domain/log.py`
- `session/derive.py` to `session/domain/derive.py`
- `session/repair.py` to `session/domain/repair.py`
- `session/change_notes.py` to `session/domain/change_notes.py`
- `session/speakers.py` to `session/domain/speakers.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.
- The session checks in `test_layering.py` still pass.

## Blocked by

15
