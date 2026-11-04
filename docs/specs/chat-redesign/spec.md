# Chat redesign

The approved mockup is [mockup.html](./mockup.html). Open it in a browser. The warm look is the one being built.

## Problem

After you press send, the chat sits blank until the bot's first word or tool call. On a local model that took 5.6 seconds, and the only sign of life was a small "working" pill in the corner. While the bot works, nothing moves. "Working…" is plain text, a finished tool just says "done", and code inside a sentence shows its backticks.

## What changes for you

1. You type a message in a bot's chat and press Enter.
2. Your message shows at once. Under it, the bot's avatar and name show with a shimmering "Thinking" and a seconds counter.
3. The header under the bot's name reads "Working · 0:01" and counts up. The bot's row in the sidebar shows a small pulsing dot.
4. A thin bar moves along the top of the message box. The box's one button is Stop.
5. The bot calls a tool. "Thinking" gives way to a line with a spinner that names the step, such as "Running file list · 1 tool".
6. Under that line, each tool shows as a card with its server and name, such as "computer file list". A running tool has a spinner, a finished one a check, and a failed one a warning with the reason.
7. Between two tool calls, the line reads "Thinking · 2 tools".
8. The reply starts to arrive. The steps fold into one line, "Used 2 tools", and the reply's text streams in with a blinking caret.
9. If tools failed, the folded line says so, such as "Used 19 tools · 17 failed".
10. The turn ends. The counter, the dot and the moving bar go away, and the header reads "Ready".
11. You click "Used 2 tools". The tool cards open under it.
12. Code inside a sentence, such as a file name, shows as a small tinted chip with no backticks.
13. While the bot works, you type a follow-up. The Stop button becomes Send, and your message is queued for after this turn.
14. You click ⋯ in the header. A menu offers "Compact" and "Clear chat". The pencil beside it opens the bot's page.
15. If your message fails to send, your message and the Thinking row go away, and the error shows, as today.
16. In a group's chat, the Thinking row shows the moment you send. The name of the bot that answers shows when its turn starts.
17. With reduced motion turned on in your system settings, nothing moves. The text still says what is happening.

## Decisions

- The look stays warm: today's colours, with grey text a little darker so it reads at 4.5:1. The neutral look was turned down at stop 1.
- Only the chat screen changes. The sidebar from the ui-layers change stays as it is, apart from the working dot.
- The Thinking row shows the moment you press send, before the server confirms. Vercel's chatbot, LibreChat and Ava Labs' Studio chat show theirs before the first word. Microsoft's Fluent guide says AI chat indicators "should appear immediately".
- Your message shows at once, drawn by the browser until the server's copy of it arrives. Today it waits for the server.
- The counter runs in the browser from the moment it sees the turn start. LibreChat, Vercel's chatbot and Ava Labs' Studio chat all time with the browser's clock. After a reload mid-turn, it starts again at 0:00, because events carry no time.
- Only the open chat's bot gets the working dot. Showing it for other bots needs the bots list to say which chats are running.
- Every reply in a bot's own chat carries the bot's name and avatar, as replies in a group's chat already do.
- The step lines are shadcn's ready-made Trace component, as the New menu is shadcn's dropdown. Its running line is in the present tense ("Running file list"), and its shimmer stops when you prefer reduced motion.
- The steps fold when the reply starts to stream, and the folded line names what was done. assistant-ui keeps the answer outside the fold the same way. If you opened the steps yourself, they stay open, as shadcn's Trace docs advise.
- The folded line counts failed tools, as shadcn's whole-turn example does ("1 command failed").
- Code inside a sentence loses its backticks. Ava Labs' Studio chat and Tailwind's own docs site remove them the same way.
- The Thinking row uses the same shimmer as the step lines, not the mockup's three bouncing dots, so one motion means "working" everywhere. To decide at approval.
- The message box has one button: Stop while the box is empty during a turn, Send otherwise.
- Compact and Clear move into a ⋯ menu, which is the same ready-made menu the sidebar's New button uses.
- Checks run by hand in the browser, as the ui-layers change did. The frontend has no test runner, and adding one is its own change. To decide at approval.

## Out of scope

- The neutral white-and-blue look.
- Any other page: Bots, Settings, Computer, setup.
- A working dot on bots whose chat is not open.
- A "Worked for 1m 06s" line, and a counter that survives a reload. Both need a time on each event.
- A layout for phones and narrow screens.
- Any change to the harness, its API or the stored events.

## How we will know it works

- Send a message to a bot on a slow model. Within a tenth of a second, the bot's avatar, name and "Thinking" show under your message.
- Watch the header while the turn runs. It reads "Working · 0:0N" and counts up each second.
- Watch a turn that calls tools. A spinner line names each tool as it runs, and each card turns from a spinner to a check.
- Watch the reply arrive. The steps fold into "Used N tools", and the text streams with a caret.
- Make a tool fail. Its card shows a warning and the reason, and the folded line counts it as failed.
- Stop the backend and send a message. The Thinking row goes away and the error shows.
- During a turn, type in the message box. The Stop button becomes Send.
- Click ⋯, then "Clear chat", and confirm. The chat empties, as today.
- Look at a reply that names a file. The name is a tinted chip with no backticks.
- Turn on Reduce motion in macOS settings and send a message. Nothing moves, and the words are the same.
- Open the same chat with the system in dark mode. Every new piece is readable.
