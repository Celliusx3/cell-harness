# 04 — Missed times, busy chats and schedules due together

**Status.** done

**What to build.** In `schedules/scheduler.py` and `timing.py`:
- after downtime, the latest missed occurrence only, carrying its due time;
- a chat that is busy is waited on through 02's start-when-free; a schedule
  whose run is still going is not started again;
- schedules due together in one chat go as one
  `[SCHEDULE REMINDER BATCH]`;
- the next time is saved after delivery; delivery history kept to 200 runs and
  30 days.

**Checks.** Fake clock: an every-minute schedule with the clock moved ten
minutes runs once, with the latest due time. A run due while the chat is busy
starts after it settles, once. Two schedules due together produce one batch
event. A restart (new scheduler over the same file) does not repeat a
delivered run.

**Blocked by.** 03
