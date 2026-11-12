# 03 — A schedule made in chat fires in the bot's chat

**Status.** done

**What to build.** The thinnest path, end to end.
- `harness/schedules/`: `models.py` (`Schedule`: id, bot id, title, prompt,
  rrule, status, `scheduled_at`, created and updated times, last delivery),
  `repository.py` (one `schedules.json`, replaced whole like the approvals
  file), `timing.py` (python-dateutil `rrulestr` and `after`; the DeepSeek
  bounds: two lines, TZID or Z, no SECONDLY, COUNT ≤ 1000, 60 s floor),
  `scheduler.py` (one task in the composition root, `aclose()`d; sleeps to the
  earliest due time with a clock passed in, capped at a minute so Mac sleep
  cannot stretch it).
- `schedule/reminder` session event in `session/models.py`, derived as a user
  message from `prompts.py` text (`[SCHEDULE REMINDER]` framing).
- `schedule_create` in `tools/native/schedule/`, offered with a disposer from
  `web/runtime.py`, withheld from scripts, refused in a group chat.
- `python-dateutil` added to `backend/pyproject.toml`.

**Checks.** With a fake clock: create a one-off a minute ahead, advance the
clock, the bot's chat log has one `schedule/reminder` turn and the schedule is
`ended`. A bad RRULE returns a typed `Failure`. Create from a group chat is
refused.

**Blocked by.** 02
