# 01 · The keyring's untested promises are tested

**Status.** open

**What to build.** Two tests in `backend/tests/unit/test_secrets.py`, on the code as it is:
- `test_a_failed_write_keeps_the_saved_keys`: with "github" saved, `os.replace` made to raise; saving "notion" raises, and "github" still opens with its key while "notion" is not saved.
- `test_the_keyring_folder_is_made_when_missing`: a service on `tmp_path / "missing" / "secrets.json"` saves a key, and it opens again from a second service on the same path.

No code under `backend/harness/` changes.

**Checks.** `uv run pytest tests/unit/test_secrets.py` passes, two more than before, and the whole backend suite stays green at 1494.

**Blocked by.** none
