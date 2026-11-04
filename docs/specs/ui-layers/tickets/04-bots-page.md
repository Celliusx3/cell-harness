# 04 A Bots page lists every bot and group

**Status:** done

**What to build.**

- `frontend/app/(chat)/bots/page.tsx` reads `listBots`, `listGroups` and `listArchivedBots`, and shows three sections: Bots, Groups and Archived.
- `frontend/components/bots/BotList.tsx` renders a bot row as its name and the start of its instructions, linked to `/bots/<id>`. Bot builder is left out, as the sidebar leaves it out.
- It renders a group row as its name and its members' names, linked to `/c/<id>`. A member id found in neither bot list is left out.
- `frontend/components/chat/ArchivedBots.tsx` moves to `frontend/components/bots/ArchivedBots.tsx`. On the page it shows its rows open, with no collapse. Restore and Delete reload the page and call `refreshSidebar`.
- `frontend/components/chat/Sidebar.tsx` loses its Archived section. Its foot gains "Bots" first, linked to `/bots`.
- `frontend/app/(chat)/bots/[id]/page.tsx`'s header reads "Bots", then the bot's name, with "Bots" linked to `/bots`. Archive opens `/bots`.

**Checks.**

- `npm run typecheck` and `npm run build` in `frontend/` pass.
- `./scripts/check-file-lengths.sh` passes.
- By hand, with the drive-cell-harness skill: with two bots, a group and an archived bot, "Bots" shows all three sections. Assistant comes first.
- By hand: click a bot. Its page opens, and "Bots" in its header leads back.
- By hand: archive that bot. The Bots page shows it under Archived, and the sidebar no longer lists it.
- By hand: "Restore" puts it back in the sidebar's Bots list. "Delete" asks first, then removes it.
- By hand: click the group. Its chat opens.

**Blocked by.** 02
