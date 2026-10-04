# Chat

A sidebar of bots, then other chats, beside the open one. A person types in the box at the bottom, presses Send, and the reply streams in under their message.

## Sub-features

- The home page opens Assistant's chat at `/c/assistant`; any chat is at `/c/<id>`.
- Other chats: earlier conversations, Telegram and Discord, answered as Assistant.
- Stop while a turn runs; a message sent while it runs is answered next.
- Clear in the header wipes the chat in place after a confirm: the turn stops, every message is deleted, and the model starts fresh. `/new` does the same on Telegram and Discord.
- `/name` in the box invokes a skill.

## How to get to it (user POV)

Open the app, type in "Send a message", press Send. Click a bot in the sidebar to open its chat.

## Driving it with Playwright MCP

`browser_navigate` to `http://localhost:4997`, `browser_type` into the textbox with placeholder "Send a message", `browser_click` "Send", then `browser_wait_for` the reply text or for "Stop" to disappear. To clear, `browser_click` "Clear", then `browser_handle_dialog` with `accept: true`; the stored chat is then one `chat/cleared` event, and nothing before it is left on disk.

## Gotchas

The open tab stops listening once a turn ends; a turn started elsewhere (Telegram, a resumed approval) shows after a reload.
