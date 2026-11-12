# Schedules

A bot asked to do something at a time, or on a repeat, calls `schedule_create`. At each due time the instruction arrives in the bot's own chat as a scheduled message, and the bot answers it there and on its linked chat apps.

## Sub-features

- In the chat, a scheduled message is an outlined bubble on the person's side: a clock, "Scheduled", the title and the due time, then the instruction. Schedules due together share one bubble.
- The Schedules page in Settings (`/settings/schedules`) lists every schedule: title, status, bot, next time (active only), last run, instruction, and Pause or Resume, Run now and Delete. Delete asks first.
- A change made on the page draws a muted line in the bot's chat, `Schedule "<title>" was changed from Settings` (or `deleted`), and the bot reads a `[SCHEDULE CHANGE]` note on its next request. Run now draws none.
- The bot can also list, view, change, pause, resume and delete its own schedules from the chat.

## How to get to it (user POV)

Ask "every minute, check the deployment and tell me how it looks", then wait a minute.

## Driving it with Playwright MCP

Send the prompt, `browser_wait_for` the bot's scheduled reply, then `browser_navigate` to `/settings/schedules` and click "Pause", "Resume", "Run now" or "Delete" (accept the confirm with `browser_handle_dialog`).

For a check with no real key, a fake OpenAI-compatible server that answers a person's message with a `schedule_create` tool call (an RRULE like `DTSTART:<now+30s, UTC>\nRRULE:FREQ=MINUTELY`) and a `[SCHEDULE REMINDER` message with text is enough. Give each tool call its own id, or the timeline warns of duplicate keys.

## Gotchas

- The schedules file is `$RUN/harness/schedules.json` in this copy, set by `HARNESS_SCHEDULES__PATH`; without it the copy writes the person's.
- An every-minute schedule keeps running while the copy is up: delete it, or stop the copy.
- The Schedules page shows its empty sentence for a moment before the list loads, like the Approvals page.
