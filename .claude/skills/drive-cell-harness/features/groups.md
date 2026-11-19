# Groups

Two to six bots share one chat. The sidebar lists groups under Groups, below Bots, and the Bots page lists each with its members' names. Your message there lines up who speaks: the members you @mention, every member when you write `@everyone`, and otherwise the group's reply setting (Everyone, Lead, Mentions or Auto). They answer one after another. A bot your message asked can bring in a teammate by @mentioning it, once per message; a bot brought in that way brings in nobody. `/goal <text>` starts a goal run instead: the lead and the members it names take turns until the lead ends it.

## Sub-features

- "New", then "Group", at the sidebar's top opens a form: a name and a checkbox per bot, numbered in the order you tick them. "Make group" is enabled once there is a name and two to six bots, and opens the group's chat at `/c/<group id>`.
- Each turn sits under the bot's colored initial and its name in bold. Its tool calls, the text between them and its notes fold into one line. It names the step while the bot works and reads "Used N tools" once the reply starts; click it to open. The last reply, a question or approval card, an error and an app view stay in sight.
- A bot with nothing to add replies `NO_RESPONSE`: its turn shows only its name and the folded line, or nothing when it used no tools.
- The group's name in the chat header opens its settings page at `/groups/<group id>`: name, members, lead ("First member" for none), "Who answers a plain message" (Everyone, Lead only, Only bots you @mention, Auto) and, for Auto, its model. Save returns to the chat.
- Auto asks the chosen model which member answers a message that names nobody. A reply it picked shows "Picked by Auto · 95%" under it; under 60% sure, the lead answers and the line says so.
- `/goal <text>` in a group starts a goal run led by an @named member in the text, else the group's lead, else the first member. A line "Goal run · led by <lead>" shows above your message. The lead hands each turn to one member with a task, through a block the chat never shows, and waits for a member's worker reports before it speaks again. It ends the run as done, needs you or blocked, or at 13 turns; a card then shows the lead, "N of 13 turns", the status and a detail. Stop ends the run and the card says Stopped.
- Answering a bot's question or approval resumes that bot's turn, then the rest of the line speaks.
- Archiving or deleting a bot stops the discussion it is speaking in. A group whose bots are all archived keeps its chat and refuses a new message with a 409.

## How to get to it (user POV)

Click "New", then "Group", at the sidebar's top, name the group, tick the bots, press Make group, and send a message in its chat.

## Driving it with Playwright MCP

`browser_click` "New", then the menu item "Group", `browser_type` the name into the Name box, click each bot's name inside the Members list (the sidebar has the same names, so pick the ones in the form), `browser_click` "Make group"; the URL becomes `/c/<group id>` and the header shows the group's name. Send the message as in [chat.md](chat.md) and `browser_wait_for` the Stop button to disappear: a discussion is one run, so it stays until the last bot in line has spoken.

## Gotchas

Who spoke each turn is `turn/start`'s `bot_id` in `/api/conversations/<group id>`; the group's roster is its `group/members` event. A local model can leak its thinking as `<|channel>thought … <channel|>` reply text; that is the model server's reasoning parsing, set per model in LM Studio, not this feature. A goal run's steps are its `goal/start`, `goal/step` and `goal/end` events; an Auto pick is `group/auto_pick`. A lead that calls `message_bot` gets a refusal in a group and goes on; it wastes a step but does not end the run.
