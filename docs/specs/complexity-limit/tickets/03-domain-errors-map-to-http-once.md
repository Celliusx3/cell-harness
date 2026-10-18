# 03 · Domain errors map to HTTP once, and the flagged route builders use it

**Status.** open

**What to build.**
- New `backend/harness/web/errors.py`: one map from each domain error to its usual status (`BotNotFound` 404, `BotPermanent` 409, `FileTooLarge` 413, `GroupEmpty` 409, `InvalidSkill` 422, `McpConnectionError` 502, `McpNotConnectedError` 503, `McpTimeoutError` 502, `SecretNotFound` 404, `SecretRefused` 409, `SessionCorruptionError` 500, `SessionFormatUnsupportedError` 500, `SessionNotFoundError` 404, `SkillNotEditable` 409, `SkillShadowed` 409, `UnreadableFile` 422, `UnsafeFileName` 422) and the handlers FastAPI takes for it, each answering `{"detail": str(err)}` with that status, as `HTTPException` does today. The web app is built with them.
- `backend/harness/web/routes/bots.py`, `skills.py`, `mcp.py` and `backend/harness/channels/web/routes.py` drop every `except` whose status and message match the map; an `except` with its own status or message stays. Each `build_router` is then 10 or under.
- A new test pins every mapped error to its status and body, and that an error a route does not catch answers its mapped status.

**Checks.** `make lint` and `make test` green, every route test's status and body unchanged. `uv run ruff check harness --select C901` reports nothing for the four builders.

**Blocked by.** none
