# 02 Every call to the app needs the login

**Status.** removed

**What to build.** A token made once in `~/.harness/web-token` (0600, outside the files root). `make dev` prints `http://localhost:4897/login?token=…`; that route sets an HttpOnly, SameSite=Strict cookie and redirects home. Every `/api` route, the event streams, the MCP App proxy and the computer's relay refuse without the cookie (401). The chat page shows "open the login link from the terminal" on a 401. Test helpers pass the cookie explicitly.

**Checks.** An integration test: `GET /api/bots` without the cookie is 401, with it 200; the login route with a wrong token is 401 and sets no cookie.

**Blocked by.** 01

**Removed, 2026-10-17.** Built and checked (401 from inside the computer), then taken out at the person's request: the app is reached over Tailscale. The risk it closed is written in the spec's Out of scope and in PHASES.md insertion 19.
