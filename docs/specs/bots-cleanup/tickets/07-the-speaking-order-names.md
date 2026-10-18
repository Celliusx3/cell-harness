# 07 · The speaking-order names say what they hold

**Status.** done

**What to build.** In `backend/harness/bots/discussion.py`: `first_line` becomes `first_speakers`, `Line` becomes `SpeakerQueue` with `waiting` and `turns_from_mentions`, `_line_after` becomes `_queue_after`, `MENTION_TURNS` becomes `MAX_TURNS_FROM_MENTIONS`, and a bot id held as `speaker` becomes `speaker_id`. Callers: `backend/harness/runs/service.py` and `backend/tests/unit/test_discussion.py`.

**Checks.** `test_discussion.py`, `test_runs.py`, `test_gateway_groups.py` and the backend suite pass before and after. Break: make `first_speakers` ignore `@everyone` beside a member's name; the new `@Writer and @everyone, go` case fails (no test held that promise before, so it is added here). Set `MAX_TURNS_FROM_MENTIONS` to 5; `test_mentions_add_at_most_six_turns_per_message_of_the_person_s` fails.

**Blocked by.** 01
