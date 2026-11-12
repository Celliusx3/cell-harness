# 05 — List, view, change, pause, resume and delete from chat

**Status.** open

**What to build.** `schedule_list`, `schedule_view` and `schedule_edit`
(update title, prompt or rrule; pause; resume; delete) in
`tools/native/schedule/`, over a `ScheduleService` in `harness/schedules/` that
the tools and the page share. Resume computes the first time after now.
Deleting a bot (`BotService.delete`) deletes its schedules.

**Checks.** Tool tests: list shows active first by next time; pause stops a
due run; resume runs at the next time after the edit; an unknown id returns a
typed `Failure`; deleting the bot empties its schedules.

**Blocked by.** 03
