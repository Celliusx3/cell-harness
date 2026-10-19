# 02 · The disk store is under repositories

**Status.** open

**What to build.** `backend/harness/secrets/disk.py` moves to `backend/harness/secrets/repositories/disk.py`, unchanged. `backend/harness/secrets/repositories/__init__.py` holds one docstring line, as `session/repositories/__init__.py` does: the concrete stores, each implementing the secrets repository contract. `secrets/__init__.py` imports `DiskSecretRepository` from its new path. `secrets/repository.py` stays beside the service.

**Checks.** The whole backend suite passes at 1497. `grep -rn "harness.secrets.disk" backend` finds nothing. `make lint` is green.

**Blocked by.** 01
