# 06 · The bots service's names say what comes back

**Status.** open

**What to build.** In `backend/harness/bots/service.py`: `find(bot_id)` becomes `active_bot(bot_id)`, `names()` becomes `active_bot_names()`, and the key-list methods name their parameter for what it holds: `allow_secret(bot_id, secret_name)`, `set_allowed_secrets(bot_id, secret_names)`, `forget_secret(secret_name)`. Callers: `backend/harness/runs/bot_messages.py`, `backend/harness/tools/native/secrets/tools.py`, `backend/harness/tools/native/bots/message.py`, and the lookups in `test_bot_service.py`, `test_bot_secrets.py`, `test_bot_builder.py`.

**Checks.** The backend suite passes before and after; `grep -rn '\.find(' backend/harness` shows no bots lookup. Break: let `active_bot` return archived bots; `test_an_archived_bot_owns_no_chat_and_cannot_be_edited` fails.

**Blocked by.** 04
