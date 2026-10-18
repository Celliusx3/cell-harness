# 07 · The speaking-order names say what they hold

**Status.** open

**What to build.** In `backend/harness/bots/discussion.py`: `first_line` becomes `first_speakers`, `Line` becomes `SpeakerQueue` with `waiting` and `turns_from_mentions`, `_line_after` becomes `_queue_after`, `MENTION_TURNS` becomes `MAX_TURNS_FROM_MENTIONS`, and a bot id held as `speaker` becomes `speaker_id`. Callers: `backend/harness/runs/service.py` and `backend/tests/unit/test_discussion.py`.

**Checks.** `test_discussion.py`, `test_runs.py`, `test_gateway_groups.py` and the backend suite pass before and after. Break: make `first_speakers` ignore `@everyone`; a discussion test fails.

**Blocked by.** 01
