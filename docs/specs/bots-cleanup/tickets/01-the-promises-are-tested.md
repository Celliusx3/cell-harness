# 01 · The promises the cleanup must keep are tested

**Status.** open

**What to build.** Two tests for promises nothing checks today, written against the code as it is:
- `backend/tests/unit/test_bot_service.py`: restoring Assistant leaves it as it was and writes no bots file.
- `backend/tests/unit/test_native_bots.py`: the `bot_create` tool's input schema is exactly the object of `name` and `instructions`, both required strings, each with its current description.

**Checks.** Both new tests pass on the code as it is; the backend suite stays green.

**Blocked by.** none
