# 09. Layer secrets: service and router

**Status.** done

## What to build

Move the code that acts and the routes of `secrets`. `sealing.py` imports `os`, so it is service code.
- `secrets/service.py` to `secrets/service/secret_service.py`
- `secrets/sealing.py` to `secrets/service/sealing.py`
- `secrets/credential_effects.py` to `secrets/service/credential_effects.py`
- `secrets/router.py` to `secrets/router/secret_router.py`
- `secrets/schemas.py` to `secrets/router/schemas.py`
- `secrets/credentials_router.py` to `secrets/router/credential_router.py`
- `secrets/credentials_schemas.py` to `secrets/router/credential_schemas.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

08
