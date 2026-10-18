# 01 · The turn loop under the limit

**Status.** open

**What to build.** In `backend/harness/runtime/turn.py`, `run_turn` (14) and `_stream_reply` (11) drop to 10 or under by naming their decisions: the end-of-step decision when a reply asks for no tools (give up, tell, or complete) becomes one helper returning the outcome or nothing; in `_stream_reply`, the failure-or-retry choice and recording an interrupted reply become helpers. The events, their order and every session append stay exactly as they are.

**Checks.** `make lint` and `make test` green (1463 passed), the turn-contract, loop, recovery and interrupt tests among them. `uv run ruff check harness/runtime/turn.py --select C901` reports nothing.

**Blocked by.** none
