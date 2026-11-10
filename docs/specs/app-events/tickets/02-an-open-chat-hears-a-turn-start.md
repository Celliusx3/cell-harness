# 02 · An open chat hears that a turn started outside it

**Status.** done

**What to build.** `RunService._begin` publishes `TurnStarted(chat_id)`. A new route file `backend/harness/web/routes/app_events.py` serves `GET /api/app-events` as server-sent events: `app/connected` first, then each published event, kept alive like the chat stream.

On the frontend, `frontend/lib/appEvents.ts` offers `useAppEvent(onEvent)`. It opens one `EventSource` while any component listens. The chat page calls `conversation.wake()` on `chat/turn-started` for its own id. On `app/connected` it calls `conversation.catchUp()`, which reads from the cursor without showing a turn as running.

**Checks.** An integration test against a real server opens `/api/app-events`, reads `app/connected`, posts a message to Assistant, and reads `chat/turn-started` naming Assistant's chat. In the browser on a scratch copy, a message sent with `curl` to an open, idle chat shows in the window.

**Blocked by.** 01
