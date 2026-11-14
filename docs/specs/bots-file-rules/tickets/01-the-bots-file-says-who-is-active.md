# 01. The bots file says who is active

**Status.** done

## What to build

Give `BotsFile` in `harness/bots/domain/models.py` three methods that only compute: `active_bots(built_ins)`, `with_bots(bots)` and `with_archived(bot_id, archived=...)`.
`BotService` in `harness/bots/service/bot_service.py` calls them. Delete `_active_bots_in`, `_save_bots`, `_save_bot` and `_set_archived` from it.
Add `tests/unit/test_bots_file.py`, which hands a `BotsFile` plain bots and checks what comes back.
No behaviour changes.

## Checks

`uv run pytest -q --no-cov` on the 13 bots test files gives 114 passed, before and after. The new file's tests pass with no repository and no service.

## Blocked by

none
