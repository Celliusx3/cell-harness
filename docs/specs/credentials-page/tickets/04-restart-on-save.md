# 04 Restart on save

**Status:** open

**What to build.**

- The `Makefile`'s `BACKEND_RUN` gains `--reload-include config.local.json`, so `make dev` restarts the harness when the file changes.
- The desktop app watches the friend's settings file and restarts only the harness child when it changes. The window and the page server stay.
- After a save, the page waits until `GET /api/credentials` answers again, then says the change is applied.

**Checks.**

- node:test on the desktop's restart decision: a change to the watched file restarts the harness, and a change during a quit does not.
- By hand in `make dev`: save a Telegram token, the harness restarts, and its log says the Telegram channel registered.
- By hand in the desktop app: save a Telegram token. The harness pid changes, and the window stays open.

**Blocked by.** 03
