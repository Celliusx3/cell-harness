# 02. Layer app_events

**Status.** open

## What to build

Move the three modules of `app_events`. Keep its public names in `__init__.py`.
- `app_events/models.py` to `app_events/domain/models.py`
- `app_events/service.py` to `app_events/service/app_event_service.py`
- `app_events/router.py` to `app_events/router/app_event_router.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

01
