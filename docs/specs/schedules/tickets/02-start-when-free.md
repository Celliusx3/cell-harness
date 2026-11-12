# 02 — Start a turn once the chat is free, in one place

**Status.** done

**What to build.** A reshaping, no change in behaviour. Move the "wait until no
run is in flight, then `hear`" loop out of `BotMessages._deliver`
(`runs/bot_messages.py`) into `RunService`, so schedules can reuse it. The
opening it starts becomes a parameter rather than a `BotMessage`.

**Checks.** The bot-message tests in `backend/tests/` pass before and after,
unchanged; `make lint` stays green.

**Blocked by.** none
