# Bots

Each bot has a name, instructions and one chat. The sidebar lists them under Bots, Assistant first. Assistant is there from the first start and cannot be deleted.

## Sub-features

- "New bot" in the sidebar header opens a form: Name, Instructions, Save. Saving opens the new bot's empty chat.
- "Edit bot" in a bot's chat header opens the same form with Delete (not for Assistant). After an edit, the chat shows "Instructions updated" before the next turn.
- From chat: ask a bot to make one ("make a bot called Translator that translates into Malay"). It calls `bot_create`, which asks first; after "Allow once" the bot appears in the sidebar when the turn ends.

## How to get to it (user POV)

Press the bot icon in the sidebar header, or ask Assistant for a new bot.

## Driving it with Playwright MCP

`browser_click` "New bot", `browser_fill_form` the "Name" and "Instructions" textboxes, `browser_click` "Save"; the URL becomes `/c/<bot id>`. From chat: send the request, `browser_wait_for` "Allow once", click it, then `browser_wait_for` the bot's name in the sidebar.

## Gotchas

The instructions are logged in the chat as a `bot/instructions` event; read them from `/api/conversations/<bot id>`, not from the bots file. Every bot sees every skill, so a skill that matches a message can pull a small model off its bot's instructions.
