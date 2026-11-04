# 03 Every chat page waits for setup

**Status:** open

**What to build.**

- `frontend/components/setup/SetupGate.tsx` wraps the `(chat)` layout's content.
- The gate reads `listCredentials`. With no credential where `is_default_model` is true, it replaces the page with `/setup`.
- It shows nothing of the chat until that answer comes. A failed read shows the error in place, as the root page does.
- `frontend/app/(chat)/layout.tsx` puts the gate around the sidebar and the page.
- `/setup` goes to `/` when a Default model already exists.
- `/setup` shows "Finish setup on the Mac that runs Cell Harness" instead of the form when `canSaveCredentials` is false.

**Checks.**

- `npm run typecheck` in `frontend/` passes.
- By hand, with the drive-cell-harness skill: before setup, `/`, `/skills` and a bot's page each go to `/setup`.
- By hand: after setup, `/setup` goes to the Assistant's chat.
- By hand: the page opened at the Mac's network address, not `127.0.0.1`, shows the note and no form.

**Blocked by.** 02
