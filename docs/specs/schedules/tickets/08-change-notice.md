# 08 — The bot is told when its schedule changes elsewhere

**Status.** open

**What to build.** A change made from the page (07) logs a `schedule/change`
event in the bot's chat, derived as a user message with the
`[SCHEDULE CHANGE]` text from `prompts.py`. It starts no turn; a running turn
sees it at its next step. A change made by the bot itself logs none.

**Checks.** Pause from the route: the bot's next request contains the change
note once. Pause through `schedule_edit` in the chat: no note.

**Blocked by.** 07
