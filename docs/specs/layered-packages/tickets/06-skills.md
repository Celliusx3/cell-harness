# 06. Layer skills

**Status.** open

## What to build

Move the ten modules of `skills`. The catalog reads skill folders from disk, so it is the repository. Update `CIRCULAR_IMPORT_RISK` in `test_layering.py` for the tool's new path.
- `skills/models.py` to `skills/domain/models.py`
- `skills/invocation.py` to `skills/domain/invocation.py`
- `skills/catalog.py` to `skills/repository/catalog.py`
- `skills/service.py` to `skills/service/skill_service.py`
- `skills/archive.py` to `skills/service/archive.py`
- `skills/prompt.py` to `skills/service/prompt.py`
- `skills/resources.py` to `skills/service/resources.py`
- `skills/tool.py` to `skills/service/tool.py`
- `skills/router.py` to `skills/router/skill_router.py`
- `skills/schemas.py` to `skills/router/schemas.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

01
