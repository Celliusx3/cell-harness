# 02 The setup screen saves the Default model

**Status:** done

**What to build.**

- `GET /api/credentials` gains `shipped_model`, a `ModelDetails` with the configured `llm.base_url` and `llm.model`.
- `backend/harness/web/routes/credentials.py` gets it from the composition root as one typed value, not a new loose parameter.
- `frontend/lib/credentials.ts` adds `shipped_model` to `CredentialList`.
- `frontend/app/setup/page.tsx` is a full-window page outside the `(chat)` group, so it has no sidebar.
- `frontend/components/setup/SetupForm.tsx` shows the API key box, Start and "Use another provider".
- The link shows the endpoint and model boxes, filled from `shipped_model`.
- Start sends `addCredential` with the name `default_model`, an `llm` details value and no bots. Then the page goes to `/`.
- A refusal shows under the form in the app's danger colours, as the Credentials dialog shows one.

**Checks.**

- A test: `GET /api/credentials` returns `shipped_model` with the config's endpoint and model.
- `npm run typecheck` in `frontend/` passes.
- By hand, with the drive-cell-harness skill: open `/setup`, paste a key and click Start. The chat answers "hi".
- By hand: Credentials lists the key as the Default model.
- By hand: "Use another provider" shows the two filled boxes, and changed values reach the Default model.
- By hand: the screen is checked in light and dark.

**Blocked by.** 01
