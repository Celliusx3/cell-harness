# 01 The harness starts with no Default model

**Status:** open

**What to build.**

- `backend/harness/web/server.py` builds the keyring without refusing when it holds no Default model.
- `require_default_model` in `backend/harness/web/file_keys.py` has no caller left, so it goes.
- `_resolve_context_tokens` returns `None` and logs a warning when there is no configured cap and no Default model.
- A turn with no Default model still fails with `SecretNotFound`, as it does today.

**Checks.**

- A test: a keyring with no Default model builds, and the harness's start does not raise.
- A test: with no configured cap and no Default model, the context window is `None`.
- The old test that expects a refusal at start is replaced by the first test.
- By hand: `make dev` on a scratch settings file with only an encryption key starts the harness.

**Blocked by.** none
