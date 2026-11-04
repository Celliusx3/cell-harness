# 03 Back to chats opens the page you left

**Status:** open

This ticket is dropped if the person picks "always open Assistant's chat" at approval.

**What to build.**

- `frontend/components/settings/chatReturn.ts` holds the saved path, a `string` kept in `sessionStorage`.
- Its `returnPathOf(saved: string | null): string` is pure. It gives back a path that starts with one `/` and not `/settings`, or `/`.
- Its `rememberChatPath(path)` saves the path, and its `chatPathToReturnTo()` reads it through `returnPathOf`.
- A failed `sessionStorage` read or write counts as nothing saved, so a private window still gets `/`.
- `frontend/components/chat/Sidebar.tsx` calls `rememberChatPath` with each `pathname` it shows.
- `frontend/components/settings/SettingsMenu.tsx`'s "Back to chats" opens `chatPathToReturnTo()`.

**Checks.**

- `npm run typecheck` and `npm run build` in `frontend/` pass.
- By hand, with the drive-cell-harness skill: open a second bot's chat, then "Settings", "Skills", "Back to chats". That bot's chat opens.
- By hand: open `/settings` in a new tab and click "Back to chats". Assistant's chat opens.
- By hand: set the saved path to `//example.com` in the console, then click "Back to chats". Assistant's chat opens.

**Blocked by.** 02
