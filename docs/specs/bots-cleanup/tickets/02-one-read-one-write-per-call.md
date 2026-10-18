# 02 · The bots service reads its file once and writes it once per call

**Status.** done

**What to build.** Only `backend/harness/bots/service.py`. The four storage helpers (`_stored`, `_stored_bots`, `_write`, `_save`) become two: `_read_file() -> BotsFile` and `_write_file(stored: BotsFile)`. Every public method reads once, builds the new `BotsFile` with `model_copy`, and writes once; bots and groups are saved the same way. `_store` becomes `_save_bot(stored, bot)`, `_set_archived` takes the file already read, `_active_bots()` becomes `_active_bots_in(stored)`, `check_removable` becomes `_check_removable(stored, bot_id)`, and the module's `_once_each` becomes `_without_repeats`. Public `active_bots()` still opens the built-in chats the first time.

**Checks.** `test_bot_service.py`, `test_groups.py`, `test_bot_secrets.py`, `test_bot_builder.py` and the whole backend suite pass before and after. Break: make saving a bot drop the groups; `test_changing_a_bot_keeps_every_group` fails.

**Blocked by.** 01
