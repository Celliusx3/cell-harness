# 03 · Sealing is named for what it returns

**Status.** open

**What to build.** `backend/harness/secrets/encryption.py` becomes `backend/harness/secrets/sealing.py` (moved with `git mv`). `seal(plaintext, *, encryption_key, record_id)` becomes `sealed(...)` and `unseal(ciphertext, *, encryption_key, record_id)` becomes `unsealed(...)`, with the same arguments, matching `redacted(text, value)` beside them. Their one caller, `secrets/service.py`, follows. The `encryption_key` argument keeps its name: it is the config setting's name.

**Checks.** The whole backend suite passes at 1497. `grep -rn "encryption import\|\bseal(\|\bunseal(" backend/harness` finds nothing. `make lint` is green.

**Blocked by.** 02
