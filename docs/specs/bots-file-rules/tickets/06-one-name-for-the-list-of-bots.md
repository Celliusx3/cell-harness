# 06. One name for the list of bots

**Status.** open

## What to build

Move every caller of `open_active_bots` to `active_bots`: `bot_router.py`, `secret_router.py`, `credential_router.py`, `schedule_router.py`, `bot_messages.py`, and 13 test files.
Delete `open_active_bots`, and the `SessionNotFoundError` import it leaves unused in `bot_service.py`.
No behaviour changes.

## Checks

`make lint` and `make test` are green before and after. `grep -rnw open_active_bots harness tests` finds nothing.

## Blocked by

05
