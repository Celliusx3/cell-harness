# Groups

Two to six bots share one chat. The sidebar lists groups under Groups, below Bots. Your message there lines up who speaks: the members you @mention, or every member in the order they were picked when you mention nobody or write `@everyone`. They answer one after another; a bot that @mentions a teammate in its reply brings it back, at most 6 times per message of yours, then the group waits for you.

## Sub-features

- "New group" (the people icon in the sidebar header) opens a form: a name and a checkbox per bot, numbered in the order you tick them. "Make group" is enabled once there is a name and two to six bots, and opens the group's chat at `/c/<group id>`.
- Each turn sits under the bot's colored initial and its name in bold. Its tool calls, the text between them and its notes fold into one line, "Working…" while it runs and "Done · N tools" after; click it to open. The last reply, a question or approval card, an error and an app view stay in sight.
- A bot with nothing to add replies `NO_RESPONSE`: its turn shows only its name and the folded line, or nothing when it used no tools.
- Answering a bot's question or approval resumes that bot's turn, then the rest of the line speaks.
- Archiving or deleting a bot stops the discussion it is speaking in. A group whose bots are all archived keeps its chat and refuses a new message with a 409.

## How to get to it (user POV)

Press the people icon in the sidebar header, name the group, tick the bots, press Make group, and send a message in its chat.

## Driving it with Playwright MCP

`browser_click` "New group", `browser_type` the name into the Name box, click each bot's name inside the Members list (the sidebar has the same names, so pick the ones in the form), `browser_click` "Make group"; the URL becomes `/c/<group id>` and the header shows the group's name. Send the message as in [chat.md](chat.md) and `browser_wait_for` the Stop button to disappear: a discussion is one run, so it stays until the last bot in line has spoken.

## Gotchas

Who spoke each turn is `turn/start`'s `bot_id` in `/api/conversations/<group id>`; the group's roster is its `group/members` event. A local model can leak its thinking as `<|channel>thought … <channel|>` reply text; that is the model server's reasoning parsing, set per model in LM Studio, not this feature. A reply that only @mentions the person's request back to a teammate can bounce until the cap of 6.
