# 03 · The turn order is private to the bots package

**Status.** done

**What to build.**
- `backend/harness/bots/discussion.py` becomes `backend/harness/bots/_turn_order.py`, unchanged inside except its first line, which says it is the turn order in a chat. `bots/service.py` imports it as a module and calls `_turn_order.first_speakers(...)` and `_turn_order.next_speaker(...)`.
- `backend/tests/unit/test_discussion.py` becomes `backend/tests/unit/test_turn_order.py`, importing from `harness.bots._turn_order`.
- `backend/tests/unit/test_layering.py`: a new test that no module under `backend/harness/<package>/` imports a private module (a name starting with `_`) of another package. It passes today.
- `PHASES.md`: the two paths that name `bots/discussion.py` and `tests/unit/test_discussion.py` follow.

**Checks.** The backend suite and lint pass before and after; `grep -rn "bots.discussion\|bots/discussion" backend PHASES.md DESIGN.md docs` finds nothing outside `docs/specs/`. Break: import `harness.bots._turn_order` from `runs/chain.py`; the new layering test fails.

**Blocked by.** 02
