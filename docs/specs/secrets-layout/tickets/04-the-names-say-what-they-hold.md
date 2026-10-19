# 04 · The names say what they hold

**Status.** open

**What to build.**
- `Secret` becomes `UnsealedSecret` in `secrets/models/secret.py`, with `secrets/__init__.py`, `secrets/service.py` and `backend/harness/tools/native/secrets/tools.py` following.
- `_typeable` becomes `_typeable_value` in `secrets/models/secret.py`, a noun phrase like its neighbours `_bare_https_origin` and `_sendable_header`.
- `OWNER_ONLY` becomes `FILE_MODE` in `secrets/repositories/disk.py`, like `FOLDER_MODE` in `images/disk.py`.
- `BLANKED_SECRET` becomes `REDACTED_SECRET` in `secrets/redaction.py`; its module docstring and the lambda's argument say "redact" too.

**Checks.** The whole backend suite passes at 1497. `grep -rnw "Secret\|OWNER_ONLY\|BLANKED_SECRET\|_typeable" backend/harness backend/tests` finds nothing. `make lint` is green.

**Blocked by.** 03
