# 01 · The shapes are a models folder, one file per subject

**Status.** open

**What to build.** `backend/harness/secrets/models.py` becomes `backend/harness/secrets/models/`, moved with no renames:
- `__init__.py`: a one-line docstring only, as `tools/models/__init__.py` has.
- `destination.py`: `SecretAuth`, `Destination` and its three validators, `_ORIGIN`, `_HEADER_TOKEN`, `_RESERVED_HEADERS`.
- `secret.py`: `SecretName`, `SECRET_VALUE_RULE`, `_TYPED_KEY`, `_typeable`, `SecretValue`, `Secret`, `SecretSummary`.
- `sealed.py`: `SealedSecret`, `SecretsFile`.
- `errors.py`: `SecretRefused`, `SecretNotFound`.

Importers move to the new paths: `secrets/__init__.py`, `secrets/service.py`, `secrets/repository.py`, `secrets/disk.py`, `backend/tests/unit/test_disk_secrets.py`. `models.py` is deleted.

**Checks.** The whole backend suite passes at 1497 before and after. `grep -rn "harness.secrets.models import" backend` names only the four new modules. `make lint` is green.

**Blocked by.** none
