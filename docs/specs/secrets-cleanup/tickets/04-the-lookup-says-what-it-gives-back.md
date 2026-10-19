# 04 · The lookup says what it gives back

**Status.** open

**What to build.** `SecretService.find(name) -> Secret | None` becomes `secret_named(name)`, with every caller: `backend/harness/tools/native/secrets/tools.py`, `backend/tests/unit/test_secret_service.py` and `backend/tests/integration/test_web_secrets.py`.

**Checks.** The whole backend suite passes at ticket 03's count. `grep -rn "\.find(" backend/harness/secrets backend/harness/tools/native/secrets backend/tests/unit/test_secret_service.py backend/tests/integration/test_web_secrets.py` finds no call on the secrets service.

**Blocked by.** 03
