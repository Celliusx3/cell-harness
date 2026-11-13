# 07. Layer tickets

**Status.** done

## What to build

Move the nine modules of `tickets`.
- `tickets/models.py` to `tickets/domain/models.py`
- `tickets/prompts.py` to `tickets/domain/prompts.py`
- `tickets/repository.py` to `tickets/repository/ticket_repository.py`
- `tickets/service.py` to `tickets/service/ticket_service.py`
- `tickets/places.py` to `tickets/service/places.py`
- `tickets/worker.py` to `tickets/service/worker.py`
- `tickets/router.py` to `tickets/router/ticket_router.py`
- `tickets/files_router.py` to `tickets/router/file_router.py`
- `tickets/schemas.py` to `tickets/router/schemas.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

01
