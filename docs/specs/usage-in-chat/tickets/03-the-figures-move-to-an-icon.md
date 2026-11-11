# 03 · The figures move to an icon beside the attach button

**Status.** done

**What to build.** After trying 01 and 02, the person wanted ZCode's shape instead. One gauge icon sits beside the attach button. Hovering or clicking it opens a card with the chat's totals. The line under each reply and the header's totals go away. The card shows exact counts, and "not reported" where a figure is missing.

Files: `frontend/components/conversation/UsageButton.tsx` (new), `usage.ts`, `Composer.tsx`, the chat page, and the reverts of `Timeline.tsx`, `ChatHeader.tsx` and `ReplyUsage.tsx`.

**Checks.**

- Drive a chat with `drive-cell-harness` on the fake model, then hover the icon. The card reads Input 61,695, Cached 51,590, Output 260, Cache hit rate 84%.
- No reply has a usage line, and the header reads only "Ready".
- Moving the pointer away closes the card. A click keeps it open.
- A chat with no reply has no icon.
- On an emulated phone, a tap on the icon opens the card.
- `npm run typecheck`, `make lint` and `make test` stay green.

**Blocked by.** 02
