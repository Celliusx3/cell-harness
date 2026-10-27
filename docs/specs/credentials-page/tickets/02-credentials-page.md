# 02 Credentials page, read-only

**Status:** done

**What to build.**

- `frontend/app/(chat)/credentials/page.tsx` shows the list from `GET /api/credentials`, in the chat's own style.
- Each row shows the key's name, description and state: "saved, ends in …a1b2", "not set", or "set by HARNESS_…".
- `frontend/lib/api.ts` and `lib/types.ts` gain the call and its typed shape.
- The sidebar gains a lock link, "Credentials", beside Keys.
- In this ticket every row is read-only.

**Checks.**

- `npx tsc --noEmit` is clean.
- By hand, with drive-cell-harness: the lock opens `/credentials`, and the three keys show only their last four characters.

**Blocked by.** 01
