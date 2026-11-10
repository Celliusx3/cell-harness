# 04 · The sidebar and the Bots page hear that the bots changed

**Status.** open

**What to build.** `BotService._write_file` publishes `BotsChanged()`. The sidebar and the Bots page call their list fetch on `bots/changed` and on `app/connected` through `useAppEvent`. Remove PR #59's bot stream: `harness/bots/changes.py`, the `/api/bots/changes` route and its frames in `harness/web/routes/bots.py`, `frontend/components/chat/useBotListChanges.ts` and `backend/tests/integration/test_web_bot_changes.py`.

**Checks.** An integration test against a real server opens `/api/app-events`, creates a bot over HTTP, and reads `bots/changed`. In the browser, a bot created with `curl` appears in the open sidebar and on the open Bots page. Archived with `curl`, it leaves the sidebar.

**Blocked by.** 02
