# Chat

A sidebar of conversations beside the open one. A person types in the box at the bottom, presses Send, and the reply streams in under their message.

## Sub-features

- A new conversation from the home page; continuing one at `/c/<id>`.
- Stop while a turn runs; a message sent while it runs is answered next.
- `/name` in the box invokes a skill.

## How to get to it (user POV)

Open the app, type in "Send a message", press Send. "New conversation" in the sidebar starts another.

## Driving it with Playwright MCP

`browser_navigate` to `http://localhost:4997`, `browser_type` into the textbox with placeholder "Send a message", `browser_click` "Send", then `browser_wait_for` the reply text or for "Stop" to disappear.

## Gotchas

The open tab stops listening once a turn ends; a turn started elsewhere (Telegram, a resumed approval) shows after a reload.
