# 01 · The run and bot services hold the app's event publisher

**Status.** done

**What to build.** A new module `backend/harness/app_events.py` with `AppEvents`, the publisher. `publish(event)` puts the event on every subscriber's queue. `subscribe()` gives one subscriber its events and removes its queue when it stops reading.

Two event models go in the same file: `TurnStarted(chat_id)`, typed `chat/turn-started`, and `BotsChanged()`, typed `bots/changed`. `RunService` and `BotService` take `events: AppEvents` in their constructors. `web/server.py` builds one and passes it to both. Every test helper and test that builds either service passes one too. Nothing publishes yet.

**Checks.** `make lint` and `make test` stay green with the same count as before. A unit test in `backend/tests/unit/test_app_events.py` shows two subscribers each get one published event, and that a subscriber that stops reading is removed.

**Blocked by.** none
