# Chat progress

What a person sees from the moment they press send until the turn ends. The design is [the chat redesign spec](../../../../docs/specs/chat-redesign/spec.md).

## Sub-features

- Your message shows at once, before the server confirms it. Under it, the bot's avatar and name show with a shimmering "Thinking" and a seconds counter. If the send fails, both go away and the error shows.
- The header reads "Working · 0:07" under the bot's name, counting up each second, and "Ready" when the turn ends. The counter runs in the browser, so a reload mid-turn starts it again at 0:00.
- The open chat's row in the sidebar shows a pulsing dot, labelled "Working", until the turn ends or you leave the chat.
- A thin bar moves along the top of the message box. The box's one button is Stop while it is empty, and Send once you type.
- While tools run, the steps line names the step. It folds to "Used N tools" when the reply starts. See [tool-cards.md](tool-cards.md).
- Every reply in a bot's own chat sits under the bot's avatar and name. In a group, "Thinking" shows with no name until a bot's turn starts.
- With Reduce motion turned on, nothing moves, and the words are the same.

## How to get to it (user POV)

Send any message. A slow model shows each stage longest. Asking for the files in the computer's home folder calls tools.

## Driving it with Playwright MCP

`browser_type` a prompt into "Send a message" and press Enter. Within a tenth of a second, `browser_snapshot` shows your message and "Thinking". Snapshot again while the header reads "Working · …" to see the steps line. The turn has ended when the header reads "Ready".

## Gotchas

"Stop" also hides while the box holds text, so it is not a sign that the turn ended. A fast model can skip "Thinking" and "Running …" between two snapshots: run the check in one `browser_run_code` that samples every 100 ms.
