# Bot messages

A bot sends another bot a message with `message_bot`. The message lands in the other bot's own chat as "Message from <sender>" and starts a turn there. When that turn ends, its answer lands in the sender's own chat as "Message from <recipient>" and starts a turn there, in which the sender passes it on to you. The sender does not wait: its turn ends right after the send.

## Sub-features

- The tool card `message_bot` reads "Sent to <name>. Its reply will arrive as a new message…". It refuses the sender itself, a name no active bot has, and any group chat.
- A recipient busy with a turn reads the message when that turn ends.
- A recipient that asks you something (a question, an approval, a key) answers "<name> is waiting for the user to answer it in its own chat."; one whose turn fails or is stopped answers "<name> stopped before it finished, and has no answer."
- A chain stops at 6 hops: the seventh `message_bot` call is refused with "this chain of bot messages has reached 6 hops".
- Archiving or deleting a bot drops a message still waiting for it; the backend log says "bot message dropped".

## How to get to it (user POV)

Make a second bot (New bot, or `POST /api/bots`). In Assistant's chat, ask it to ask that bot something. When Assistant's turn ends, reload the page to see the answer arrive.

## Driving it with Playwright MCP

Send the message as in [chat.md](chat.md), for example "Use message_bot to ask Researcher what the capital of Australia is." (a small local model follows the tool's name more reliably than a paraphrase). `browser_wait_for` the Stop button to disappear, then poll `curl -s localhost:<backend>/api/conversations/assistant` until `running` is false and a second `turn/start` has appeared, then `browser_navigate` to the same URL to reload. Open the other bot from the sidebar to see "Message from Assistant" and its answer.

## Gotchas

An open tab does not show the turn the answer starts until it is reloaded: the stream ends with the sender's turn, and only a send of its own wakes it. Telegram and Discord do not hear that turn either. The messages are `bot/message` events in each chat's log, with `from_name`, `hop` and `intent` (`request` or `result`); the bubble is drawn on the person's side for now.
