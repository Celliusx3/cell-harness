# 07 The bot asks before acting on a site

**Status.** done

**What to build.** The `computer` server's instructions and its
`browser_act` description in `tools/descriptions.py` tell the bot to ask first.
Before a click that sends, posts, pays or deletes, it calls `ask_user` and
waits for the answer. This is the bot's judgement and is not enforced.

**Checks.** Drive the app with the `drive-cell-harness` skill. On a test page
with a Send button, ask a bot to send a message. The chat shows a question
before any click on Send.

**Blocked by.** 01
