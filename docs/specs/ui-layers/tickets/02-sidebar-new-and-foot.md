# 02 The sidebar has one New button and labelled links at its foot

**Status:** open

**What to build.**

- `npx shadcn add dropdown-menu` writes `frontend/components/ui/dropdown-menu.tsx` on Base UI. It is generated, so nothing edits it.
- `frontend/components/chat/NewMenu.tsx` is a labelled "New" button. Its menu holds "Bot" for `/bots/new` and "Group" for `/groups/new`.
- `frontend/components/chat/Sidebar.tsx` keeps the app's name and `NewMenu` at its top. All six header icons go.
- The sidebar's foot shows "Computer" and "Settings" links with their icons and names. "Computer" keeps today's check for a connected `computer` server.
- `desktop/src/main.ts`'s `showCredentials` loads `/settings/credentials`.

**Checks.**

- `npm run typecheck` and `npm run build` in `frontend/` pass.
- `npm test` in `desktop/` passes.
- `./scripts/check-file-lengths.sh` passes.
- By hand, with the drive-cell-harness skill: "New", then "Bot", opens "What kind of bot do you want?".
- By hand: "New", then "Group", opens the New group form.
- By hand: the foot's "Settings" opens Credentials inside Settings.
- By hand: with `computer` in `mcp.servers`, the foot's "Computer" opens the Computer page. Without it, no Computer link shows.

**Blocked by.** 01
