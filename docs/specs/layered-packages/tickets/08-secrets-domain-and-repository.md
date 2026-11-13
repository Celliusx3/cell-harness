# 08. Layer secrets: domain and repository

**Status.** done

## What to build

Move the data, the pure rules and the storage of `secrets`. Delete the empty `models/` and `repositories/` folders.
- `secrets/models/destination.py` to `secrets/domain/destination.py`
- `secrets/models/details.py` to `secrets/domain/details.py`
- `secrets/models/errors.py` to `secrets/domain/errors.py`
- `secrets/models/sealed.py` to `secrets/domain/sealed.py`
- `secrets/models/secret.py` to `secrets/domain/secret.py`
- `secrets/masking.py` to `secrets/domain/masking.py`
- `secrets/redaction.py` to `secrets/domain/redaction.py`
- `secrets/repository.py` to `secrets/repository/secret_repository.py`
- `secrets/repositories/disk.py` to `secrets/repository/disk_secret_repository.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

01
