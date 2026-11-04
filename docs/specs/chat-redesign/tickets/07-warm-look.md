# 07 Small text reads at 4.5:1, and your messages are tinted

**Status:** done

Measured on the running app before this ticket, light mode: grey text on the page background reads at 4.74:1. On the grey surfaces of the sidebar and the tool cards it reads at 4.33:1. The orange "Working · 0:07" label reads at 4.22:1, and red error text on a failed card at 4.41:1. Dark mode passes everywhere.

**What to build.**

- `frontend/app/globals.css`: the light `--color-ink-soft` goes from 54% to 50% lightness, and the light `--color-danger` from 55% to 50%. The dark values stay.
- `frontend/components/conversation/ChatHeader.tsx`: the "Working · 0:07" text turns grey. The pulsing dot stays orange.
- `frontend/components/conversation/Message.tsx`: your messages use the warm tint (`accent-soft`) with a smaller bottom-right corner. Queued messages keep their faded look.

**Checks.**

- `npm run typecheck` and `npm run build` in `frontend/` pass. `make lint` passes.
- In the browser, grey text measures 4.5:1 or more on the page, on the grey surfaces and on white, in light and dark.
- Red text on a failed card measures 4.5:1 or more in both themes.
- By hand, with the drive-cell-harness skill: your messages are tinted. A queued one is faded, as today.

**Blocked by.** none
