# 03. Layer relay

**Status.** done

## What to build

Move the four modules of `relay`. `entry.py` imports the service, so it is service code.
- `relay/models.py` to `relay/domain/models.py`
- `relay/service.py` to `relay/service/relay_service.py`
- `relay/entry.py` to `relay/service/entry.py`
- `relay/router.py` to `relay/router/relay_router.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

01
