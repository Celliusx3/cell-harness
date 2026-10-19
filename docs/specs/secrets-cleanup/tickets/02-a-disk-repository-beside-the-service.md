# 02 · The keyring's disk repository and its contract, beside the service

**Status.** done

**What to build.** In `backend/harness/secrets/`:
- `repository.py`: the `SecretRepository` protocol, `sealed_secrets() -> tuple[SealedSecret, ...]` (every saved key, sealed; `()` when there is no file) and `replace_all(secrets: tuple[SealedSecret, ...]) -> None` (the keyring replaced whole).
- `disk.py`: `DiskSecretRepository(path)`, a frozen dataclass, with the storage half of `SecretService`: the file parsed as `SecretsFile`, written to an owner-only temp file in the same folder and renamed into place, the folder made when missing. `OWNER_ONLY` moves here with it.
- `__init__.py` exports `DiskSecretRepository`; the protocol is not re-exported.

`SecretService` is unchanged; ticket 03 hands it the repository.

**Checks.** `backend/tests/unit/test_disk_secrets.py` tests the disk class alone, with no encryption key: no file means no sealed keys; keys replaced whole read back equal; the file is mode 0600; the folder is made when missing; a failed rename keeps the old keys; a malformed file raises without showing its content (the five cases of today's service test). All pass, and the whole backend suite stays green.

**Blocked by.** 01
