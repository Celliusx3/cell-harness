# 01 Settings is its own screen

**Status:** open

**What to build.**

- `frontend/app/settings/layout.tsx` puts `SetupGate` around `SettingsMenu` and the page. It is a nested layout under `frontend/app/layout.tsx`, not a second root layout.
- `frontend/components/settings/SettingsMenu.tsx` shows "Back to chats", then "Credentials", "Approvals" and "Skills". `usePathname` marks the open item, as the sidebar marks its rows.
- In this ticket, "Back to chats" opens `/`.
- `frontend/app/settings/page.tsx` redirects to `/settings/credentials`.
- `git mv` moves the `credentials`, `approvals` and `skills` folders from `frontend/app/(chat)/` to `frontend/app/settings/`. Their pages do not change.
- `frontend/next.config.ts` gains `redirects()` from `/credentials`, `/approvals` and `/skills` to their `/settings/` addresses.
- The sidebar's three icons now reach Settings through those redirects. Ticket 02 replaces them.

**Checks.**

- `npm run typecheck` and `npm run build` in `frontend/` pass.
- `./scripts/check-file-lengths.sh` passes.
- By hand, with the drive-cell-harness skill: `/settings` opens Credentials with the Settings menu and no chat sidebar.
- By hand: "Approvals" and "Skills" in the menu open their pages, each marked in the menu.
- By hand: `/credentials`, `/approvals` and `/skills` each open their page inside Settings.
- By hand: "Back to chats" opens Assistant's chat without a full page reload.
- By hand: before setup, `/settings/skills` goes to `/setup`.

**Blocked by.** none
