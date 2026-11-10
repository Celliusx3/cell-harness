# App events: one stream that tells every open window what changed

## Problem

PR #59 makes an open window see changes made outside it, but it does so with two different waiting tricks. The chat's own stream waits for the next turn instead of ending, and the bots get a second stream with a change counter. Neither reads as "the server tells the app what happened", so the code is hard to follow.

## What changes for you

Nothing a person sees changes from PR #59. The code reads differently:

1. The app opens one stream when it starts, and keeps it open.
2. When a turn begins in any chat, the server publishes "a turn started in chat X" into every open stream.
3. When the bots or groups change, the server publishes "the bots changed".
4. A window with chat X open hears that event and opens the chat's stream again, as after its own send.
5. The sidebar and the Bots page hear the second event and fetch their list again.
6. The chat's own stream goes back to how `main` has it. It sends a turn's content and ends when the turn ends.
7. When the app stream drops and connects again, the server first says "connected". The open chat and the lists treat that as a change, so nothing missed while away stays missed.

## Decisions

- One stream per window for the whole app, carrying small events that name what changed, never the content. DeepSeek Harness does this (`$events` with `api-session/added`, `api-session/status`).
- Each chat keeps its own stream with a cursor for the turn's content. DeepSeek Harness, Rakazo and OpenManus all keep a stream per chat.
- Missed events are not replayed. A reconnect makes the listeners fetch again. DeepSeek Harness, Rakazo and EGC all fetch again after a reconnect.
- The stream is server-sent events, as the chat's stream already is. DeepSeek Harness and EGC use a WebSocket, but nothing here sends from the browser on it.
- The publisher lives in the backend beside the services that publish, and the web server only reads from it. The run and bot services do not know about the web.

## Out of scope

- Telegram and Discord. They already hear their own chats through the gateway.
- Events for anything else: approvals, MCP servers, credentials, skills.
- A badge for a chat that is not open. The sidebar's working dot stays as it is.

## How we will know it works

- With a chat open and idle, send a message to it with `curl`. The window shows the message and the reply as it streams, then "Ready".
- With any page open, create a bot with `curl`. It appears in the sidebar. Archive it with `curl`. It disappears.
- With the Bots page open, create a bot with `curl`. It appears in the list.
- Stop the backend and start it again with a chat open. Send a message with `curl`. The window still shows it.
- `make lint` and `make test` stay green. Today: 1757 tests pass.
