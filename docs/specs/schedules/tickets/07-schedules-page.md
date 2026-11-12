# 07 — Settings → Schedules

**Status.** done

**What to build.** HTTP routes in `web/routes/schedules.py` over `ScheduleService`: list,
pause, resume, run now, delete. A `frontend/app/settings/schedules/page.tsx`
list page in the shape of the Approvals page, and an entry in `SettingsMenu`.
Run now delivers at once and leaves the next time where it was.

**Checks.** Route tests for each action. Driven with `drive-cell-harness`:
the page lists a schedule; Pause, Resume, Run now and Delete each change what
the page shows.

**Blocked by.** 05
