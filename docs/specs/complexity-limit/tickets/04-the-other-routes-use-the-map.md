# 04 · The other route files use the map

**Status.** done

**What to build.** `backend/harness/web/routes/client.py`, `compact.py`, `groups.py`, `secret_card.py` and `secrets.py` drop every `except` whose status and message match the map. The three that give `BotNotFound` its own meaning stay: 422 in `create_group`, 409 in `client.py` and `secret_card.py`; so do the ones with their own message.

**Checks.** `make lint` and `make test` green, every route test's status and body unchanged. A search for `except` blocks in the route files that repeat the map's status with `detail=str(err)` finds only the three kept on purpose.

**Blocked by.** 03
