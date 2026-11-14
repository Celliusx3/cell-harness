# 01. The repository fetches and updates one bot

**Status.** done

## What to build

`BotsFile` in `harness/bots/domain/models.py` holds its two fields, `bots` and `groups`, and has no methods.
`BotRepository` in `harness/bots/repository/bot_repository.py` gains `bots()`, `find(bot_id)`, `add(bot)`, `update(*bots)`, `delete(bot_id)`, `groups()` and `add_group(group)`. Its whole-file read and write become private.
`update` swaps each given bot in for the stored bot with the same id, in its place. A given bot that is not stored yet goes first.
`BotService` in `harness/bots/service/bot_service.py` calls those methods and never names `BotsFile`. It works out the active bots in a private helper. Delete `_active_bots_in`, `_save_bots`, `_save_bot` and `_set_archived` from it.
Add `tests/unit/test_bot_repository.py`, which gives a `BotRepository` a file in a temporary folder and checks what it stores.
No behaviour changes.

## Checks

`make lint` and `make test` are green. The tests in `tests/unit/test_bot_repository.py` pass with no service. `tests/unit/test_bot_service.py` checks which bots are active. `grep -rnw BotsFile harness/bots/service` finds nothing.

## Blocked by

none
