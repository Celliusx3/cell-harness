# 05 The open chat's bot pulses in the sidebar while it works

**Status:** done

**What to build.**

- `frontend/components/chat/workingChat.ts` is a small store: `announceWorking(chatId, working)` and `useWorkingChat()`. `Sidebar.tsx` reads it, and the working chat's row shows a small pulsing dot labelled "Working".
- `frontend/app/(chat)/c/[id]/page.tsx` calls `announceWorking` when `running` changes, and with `false` when it leaves the chat.

**Checks.**

- `npm run typecheck` and `npm run build` in `frontend/` pass. `make lint` passes.
- By hand, with the drive-cell-harness skill: send a message. The bot's sidebar row shows the dot until the turn ends.
- By hand: open another bot's chat mid-turn. The dot goes away.

**Blocked by.** none
