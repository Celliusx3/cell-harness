# 02 · Frontend: the API call and the picker's constants

**Status.** done

**What to build.** `setMode` in `frontend/lib/api.ts` becomes `setConversationMode`. The state setter `setChatMode` in `useConversation.ts` becomes `setMode`. In `ModePicker.tsx`, `AUTO_CONFIRMATION`, `AUTO_CONSEQUENCE` and `TRIGGER_LOOK` become `AUTO_CONFIRM_TITLE`, `AUTO_CONFIRM_TEXT` and `TRIGGER_CLASSES`.

**Checks.** `npm run typecheck` is clean, and no old name is left in `frontend/`.

**Blocked by.** none
