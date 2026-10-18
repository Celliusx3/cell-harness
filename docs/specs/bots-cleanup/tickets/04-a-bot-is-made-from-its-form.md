# 04 · A bot is made and edited from its form

**Status.** open

**What to build.** `BotService.create(draft: BotDraft)` and `BotService.update(bot_id, draft: BotDraft)` replace the `name, instructions` pairs, as `create_group(draft)` already takes its draft. Callers: `backend/harness/web/routes/bots.py`, `backend/harness/tools/native/bots/tools.py`, and the tests that make or edit bots (about 46 calls in `test_bot_service.py`, `test_groups.py`, `test_bot_secrets.py`, `test_bot_messages.py`, `test_bot_turns.py`, `test_gateway_groups.py`, `test_runs.py`, `test_runs_stop.py`, `test_web_secret_access.py`, `test_web_secrets.py`).

**Checks.** The backend suite passes before and after. Break: have `create` save the draft's name as the instructions; the bot service tests fail.

**Blocked by.** 02
