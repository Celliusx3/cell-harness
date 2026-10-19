# 03 · The secrets service keeps the rules and is handed its repository

**Status.** done

**What to build.**
- `backend/harness/secrets/service.py`: `SecretService(repository: SecretRepository, *, encryption_key: str)`. It keeps the blank-key refusal, the one-site-per-name refusal, the cap, the record id and the sealing, and reads and writes only through the repository. Its file helpers, and the `os.fchmod`, `tempfile` and `Path` uses, are gone. `MAX_SECRETS` moves here from `models.py`.
- `backend/harness/web/server.py` builds `SecretService(DiskSecretRepository(settings.secrets.path), encryption_key=...)`.
- `backend/tests/webapp.py`, `backend/tests/integration/test_web_secrets.py` and `backend/tests/integration/test_web_secret_access.py` build it the same way.
- `backend/tests/unit/test_secrets.py` becomes `test_secret_service.py`. Its tests of the file alone (no file means no keys, the malformed file, the failed write, the missing folder) move to `test_disk_secrets.py` under the same names; the ones that already exist there from ticket 02 are not duplicated.

It is over five files because the constructor changes in one go.

**Checks.** The whole backend suite passes at ticket 02's count. `grep -rn "SecretService(tmp_path\|SecretService(path\|SecretService(settings" backend` finds nothing, and `secrets/service.py` imports neither `tempfile` nor `pathlib`. Starting the app with an existing keyring lists its keys on the Keys page.

**Blocked by.** 02
