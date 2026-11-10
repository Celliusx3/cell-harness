# 02 · An open chat hears that a turn started outside it

**Status.** done

**What to build.** `RunService._begin` publishes `TurnStarted(chat_id)`. A new route file `backend/harness/web/routes/app_events.py` serves `GET /api/app-events` as server-sent events: `app/connected` first, then each published event, kept alive like the chat stream. On the frontend, `frontend/lib/appEvents.ts` opens one `EventSource` for the app and offers `useAppEvent(type, handler)`. The chat layout opens it. The chat page calls `conversation.wake()` on `chat/turn-started` for its own id, and on `app/connected`.

**Checks.** An integration test against a real server opens `/api/app-events`, reads `app/connected`, posts a message to Assistant, and reads `chat/turn-started` naming Assistant's chat. In the browser on a scratch copy, a message sent with `curl` to an open, idle chat shows in the window.

**Blocked by.** 01
