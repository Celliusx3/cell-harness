# 03 · The chat's stream ends when the turn ends, as on main

**Status.** open

**What to build.** Remove the long poll from PR #59. `harness/channels/web/routes.py` loses `first_source`. `sse_frames` in `harness/channels/web/sse.py` takes its first source as a value again. `RunService` loses `next_run` and its `_started` event, and `_begin` stays as the one place a run starts and publishes.

`backend/tests/integration/test_web.py` and `frontend/components/conversation/useConversation.ts` go back to how `main` has them. `backend/tests/integration/test_web_idle_stream.py` is deleted, since ticket 02's test covers the case.

**Checks.** `make lint` and `make test` stay green. The browser check from ticket 02 still passes. `git diff origin/main -- backend/harness/channels/web` is empty.

**Blocked by.** 02
