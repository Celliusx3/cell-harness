# 15. Layer session: domain data

**Status.** done

## What to build

Move the event data of `session`. Rewrite the session checks in `test_layering.py` to read `session/domain/`.
- `session/models.py` to `session/domain/models.py`
- `session/compaction.py` to `session/domain/compaction.py`
- `session/heard.py` to `session/domain/heard.py`
- `session/images.py` to `session/domain/images.py`
- `session/schedule_change.py` to `session/domain/schedule_change.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.
- The session checks in `test_layering.py` still pass, now for the folder.

## Blocked by

01
