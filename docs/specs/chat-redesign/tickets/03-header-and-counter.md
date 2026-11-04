# 03 The header says "Working · 0:07", and Compact and Clear move into ⋯

**Status:** done

**What to build.**

- `frontend/components/conversation/useElapsed.ts` is new. `useElapsed(active)` notes the browser's time when `active` turns true, and returns the time since as "0:07" or "1:12", ticking each second. It returns null while `active` is false. The page passes `running || sending !== null`, so a snapshot that loads mid-turn starts at 0:00.
- `frontend/components/conversation/ChatHeader.tsx` is new. It shows the avatar, the name, then "Working · 0:07" or "Ready". A pencil links to the bot's page, for bots only. A ⋯ button opens the shadcn dropdown with "Compact" and "Clear chat". "Clear chat" keeps today's confirmation.
- `frontend/app/(chat)/c/[id]/page.tsx` swaps its header for `ChatHeader`.
- `frontend/components/conversation/ThinkingRow.tsx` shows the same counter after "Thinking".

**Checks.**

- `npm run typecheck` and `npm run build` in `frontend/` pass. `make lint` passes.
- By hand, with the drive-cell-harness skill: send a message. The header reads "Working · 0:00", then "0:01", "0:02" each second. The Thinking row shows the same count.
- By hand: when the turn ends, the header reads "Ready".
- By hand: click ⋯, then "Clear chat", and confirm. The chat empties. Click ⋯, then "Compact". It runs as today.
- By hand: in a group's chat, the header has no pencil.

**Blocked by.** 01
