# Chat

A sidebar of bots, then any archived ones, beside the open bot's chat. A person types in the box at the bottom, presses Send, and the reply streams in under their message.

## Sub-features

- The home page opens Assistant's chat at `/c/assistant`; any chat is at `/c/<id>`.
- A linked Telegram or Discord direct chat writes into its bot's chat, and a Discord server into Assistant's; their turns show here after a reload.
- While a turn runs, the box's one button is Stop. Once you type, it becomes Send, and the message is answered after this turn.
- "Clear chat" is in the header's "More" menu. After a confirm, it wipes the chat in place: the turn stops, every message is deleted, and the model starts fresh. `/new` does the same on Telegram and Discord.
- `/name` in the box invokes a skill.

## How to get to it (user POV)

Open the app, type in "Send a message", press Send. Click a bot in the sidebar to open its chat.

## Driving it with Playwright MCP

`browser_navigate` to `http://localhost:4997`, `browser_type` into the textbox with placeholder "Send a message", `browser_click` "Send". Then `browser_wait_for` the reply text, or for the header to read "Ready". To clear, `browser_click` "More", then "Clear chat". Then `browser_handle_dialog` with `accept: true`; the stored chat is then one `chat/cleared` event, and nothing before it is left on disk.

## Gotchas

The open tab stops listening once a turn ends; a turn started elsewhere (Telegram, a resumed approval) shows after a reload.
