# 06 Hide Computer

**Status:** done

**What to build.** `harness/web/routes/mcp.py` gains `GET /api/mcp`, which returns the configured server ids as a typed list. `frontend/lib/api.ts` reads it. `frontend/components/chat/Sidebar.tsx` shows the Computer link only when the computer server is in that list.

**Checks.** A route test: two configured servers give both ids, and none gives an empty list. Then run the harness with the app's settings, and the sidebar has no Computer link. Run `make dev`, and the link is there.

**Blocked by.** none
