# 05 · The browser shows the mode, switches it, and marks each switch

**Status.** open

**What to build.** `ConversationDetail` gains `mode`, the chat's current mode with the default applied. The message box shows a picker with Ask and Auto. Picking Auto first shows a confirm dialog, "Let this bot act without asking in this chat?". Picking Ask switches at once. Both call `PUT …/mode` through `lib/api.ts`.

The timeline draws each `approval/mode` event as one line, "Mode: Auto" or "Mode: Ask". Files: `channels/web/schemas.py`, `frontend/lib/types.ts`, `frontend/lib/api.ts`, `frontend/components/conversation/Composer.tsx`, `frontend/components/conversation/buildTimeline.ts`.

**Checks.** Drive the app with the `drive-cell-harness` skill. A new chat shows Ask, and a memory write shows a card. Pick Auto and confirm, and the timeline shows "Mode: Auto".

The next write runs with no card. Reload, and it still shows Auto. Cancelling the dialog keeps Ask. Frontend type check and lint pass, and `make test` stays green.

**Blocked by.** 01
