# 05. Layer schedules

**Status.** open

## What to build

Move the seven modules of `schedules`.
- `schedules/models.py` to `schedules/domain/models.py`
- `schedules/timing.py` to `schedules/domain/timing.py`
- `schedules/repository.py` to `schedules/repository/schedule_repository.py`
- `schedules/service.py` to `schedules/service/schedule_service.py`
- `schedules/scheduler.py` to `schedules/service/scheduler.py`
- `schedules/router.py` to `schedules/router/schedule_router.py`
- `schedules/schemas.py` to `schedules/router/schemas.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

01
