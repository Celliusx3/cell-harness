# Bots

Each bot has a name, instructions and one chat. The sidebar lists them under Bots, Assistant first. Assistant and Bot builder are there from the first start and cannot be archived or deleted; Bot builder is not listed in the sidebar, its chat is `/c/builder`.

## Sub-features

- "New bot" in the sidebar header opens "What kind of bot do you want?" with four kinds, numbered 1 to 4. Picking one puts its sentence in the message box to finish. Sending clears Bot builder's chat, sends the message there and opens `/c/builder`, where it asks up to two questions as buttons, then calls `bot_create`, which asks first.
- "Edit bot" in a bot's chat header opens the same form with Archive (not for Assistant). After an edit, the chat shows "Instructions updated" before the next turn.
- Archived in the sidebar, collapsed with a count, lists archived bots with Restore and Delete. An archived bot's chat is a 404; Delete asks first and removes the bot and its chat for good.
- From chat: ask a bot to make one ("make a bot called Translator that translates into Malay"). It calls `bot_create`, which asks first; after "Allow once" the bot appears in the sidebar when the turn ends.

## How to get to it (user POV)

Press the bot icon in the sidebar header, or ask any bot for a new bot.

## Driving it with Playwright MCP

`browser_click` "New bot", click a kind (its label, for example "Markets & money"), `browser_type` the rest of the sentence into "Send a message" with `slowly: true` so it lands after the sentence, `browser_click` "Send"; the URL becomes `/c/builder`. Answer its question buttons, `browser_wait_for` "Allow once", click it, then `browser_wait_for` the bot's name in the sidebar. From chat: send the request, `browser_wait_for` "Allow once", click it, then `browser_wait_for` the bot's name in the sidebar.

## Gotchas

The instructions are logged in the chat as a `bot/instructions` event; read them from `/api/conversations/<bot id>`, not from the bots file. Every bot sees every skill, so a skill that matches a message can pull a small model off its bot's instructions. On a small model Bot builder's first `ask_user` may leave out the question; the chat shows "Not asked. The question did not fit." and the retry shows the card. Archive on Bot builder's Edit bot page is refused with a 409.
