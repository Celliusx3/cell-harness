# 01. Add one test for every layered package

**Status.** done

## What to build

Add a test to `backend/tests/unit/test_layering.py` that finds every `harness/<package>/domain/` folder.
Each domain module must import nothing from its own package's `repository`, `service` or `router` folders.
It must also import no input or output module: `os`, `httpx`, `sqlite3`, `socket`, `aiofiles`, `tempfile`, `shutil`, `subprocess`, `zipfile`, `fastapi`.
Today it checks `bots` only.

## Checks

- `uv run pytest tests/unit/test_layering.py` passes on the code as it is.
- Change `bots/domain/turn_order.py` to import `harness.bots.service.bot_service`. The new test fails. Undo it.

## Blocked by

none
