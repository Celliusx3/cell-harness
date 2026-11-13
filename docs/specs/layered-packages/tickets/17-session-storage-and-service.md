# 17. Layer session: storage and service

**Status.** done

## What to build

Move the storage and the service of `session`. Delete the empty `repositories/` folder.
- `session/repository.py` to `session/repository/session_repository.py`
- `session/repositories/jsonl.py` to `session/repository/jsonl_session_repository.py`
- `session/service.py` to `session/service/session_service.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.
- The check that the service depends on the port, not the backend, still passes.

## Blocked by

16
