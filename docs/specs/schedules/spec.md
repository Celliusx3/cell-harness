# Schedules

Issue: [#69](https://github.com/Celliusx3/cell-harness/issues/69). Also closes
[#85](https://github.com/Celliusx3/cell-harness/issues/85).

## Problem

A bot only acts when someone sends it a message. Take "every Monday at 9, tell
me on Telegram if AAPL is under $200". The person must come back and ask each time.
And when something other than the person wakes a bot, a chat app linked to it
never hears the reply.

## What changes for you

1. On Telegram you tell Assistant: "every weekday at 9, check the deployment and
   tell me how it looks".
2. Assistant answers that the schedule "Check the deployment" is set. It says
   the next time it runs, in your time zone.
3. At 9:00 the next weekday, Assistant's chat receives the instruction as a
   scheduled message. Assistant does the work with its tools and answers.
4. The answer arrives on Telegram and in the browser chat. There, the opening
   message is drawn as a scheduled message, not as one you typed.
5. You ask "what have I scheduled?" and Assistant lists your schedules with
   their next time.
6. You say "pause the deployment check". It stops running until you say
   "resume it", and then it runs at the next time after that.
7. In the browser, Settings → Schedules lists every schedule with its bot, next
   time and last run. You can pause, resume, run now, or delete one there.
8. You change a schedule on that page. The bot's chat gets a short note that
   it changed, so the bot does not act on old information.
9. Your Mac sleeps over a weekend. When it wakes, each repeating schedule runs
   once, for its latest missed time. The bot is told the time it was due.
10. You delete a bot. Its schedules are deleted with it.

## Decisions

1. Four tools: `schedule_create`, `schedule_list`, `schedule_view`,
   `schedule_edit` (update, pause, resume, delete). DeepSeek Harness.
2. The model writes timing as one RRULE: a `DTSTART` line with a time zone, then
   an `RRULE` line. A one-off is `FREQ=DAILY;COUNT=1`. DeepSeek Harness. Read
   with python-dateutil (BSD, depends only on `tzdata`), which
   icalendar and recurring-ical-events are themselves built on.
3. Every schedule names its time zone, and local clock time holds across
   daylight saving. DeepSeek Harness, python-dateutil.
4. A schedule runs at most once a minute. DeepSeek Harness.
5. A run happens in the bot's own chat. DeepSeek Harness's "this session"
   target; its "new conversation" targets do not apply, since a bot has one chat.
6. The run opens with a user-role message headed `[SCHEDULE REMINDER]`. It
   says "This is a scheduled message from the user", then gives the schedule's
   id, due time and instruction. Schedules due together in one chat arrive as one
   `[SCHEDULE REMINDER BATCH]`. DeepSeek Harness. It is its own kind of event
   in the chat's log, like a bot's message.
7. A busy chat is waited on, and a schedule whose run is still going is not
   started again. DeepSeek Harness; this project's bot messages wait the same way.
8. After downtime only the latest missed time runs. The schedule's next time is
   saved after the run is delivered, so a crash can deliver one twice.
   DeepSeek Harness.
9. Creating a schedule does not ask first; the person can add the schedule
   tools to the tools that need approval. DeepSeek Harness. Differs from #69,
   agreed in the grill.
10. Every run's answer is shown; there is no silent run. DeepSeek Harness.
    Differs from #69, agreed in the grill.
11. A scheduled run may create schedules. Subagents cannot: they are not
    offered the tools. DeepSeek Harness. Differs from #69, agreed in the grill.
12. A change made outside the chat adds a `[SCHEDULE CHANGE]` note to that
    chat for its next step. The note starts no turn. DeepSeek Harness.
13. Each schedule keeps its newest 200 runs, up to 30 days back. DeepSeek Harness.
14. No limit on how many schedules a bot has. DeepSeek Harness.
15. A run's answer reaches every chat app linked to the bot. A bot's answer to
    another bot reaches them the same way (#85). Rakazo delivers this way.
16. No schedules in group chats, the same as messages between bots.
17. **To decide at approval.** The Schedules page lists, pauses, resumes, runs
    now and deletes. Creating and editing happen by asking a bot. DeepSeek's
    page also has a form to create and edit, with a timing editor. That editor
    is most of its page's code. Grill answer 14 included it.

## Out of scope

- A form for creating or editing a schedule on the page (decision 17).
- Sending a run to a new conversation each time.
- Schedules in group chats.
- Runs while the app is closed: the app must be running, as in DeepSeek Harness.
- Reminders to the person while a run waits on them, and giving up (#79).
- Webhooks (#82).

## How we will know it works

1. Ask a bot on Telegram for a schedule two minutes from now. Within a minute
   after the time, the answer arrives on Telegram.
2. Message a bot from Assistant while talking to Assistant on Telegram. The
   other bot's answer wakes Assistant, and Assistant's reply arrives on
   Telegram.
3. Ask for "every minute". Close the app for five minutes and open it. The
   schedule runs once, and the message names the time it was due.
4. Keep a bot busy on a long task when a schedule falls due. The run starts
   after the task ends, once.
5. Pause a schedule on the page. It does not run at its time, and the bot's
   chat shows the change note on its next message. Resume it; it runs at the
   next time.
6. Press Run now on the page. It runs straight away, and its next time does not
   move.
7. Delete the bot. Its schedules are gone from the page.
8. Ask for a schedule in a group chat. The bot is told it cannot.
