# 02. Names that say what comes back

**Status.** done

## What to build

Rename `BotService.forget_secret` to `forget_credential`, with its caller in `harness/secrets/service/credential_effects.py` and its tests.
Delete `BotService.active_bot_names`. Its one caller, `harness/tools/native/bots/message.py`, reads the names from `active_bots()`.
`bot_instructions_event` stays where it is. Moving three lines to a new file only adds a file.
No behaviour changes.

## Checks

The 114 bots tests pass before and after. `grep -rnw forget_secret harness tests` and `grep -rnw active_bot_names harness tests` find nothing.

## Blocked by

01
