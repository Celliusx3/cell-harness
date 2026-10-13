# Needs you

A bot that reaches a step only the person should do on the computer (a password, a two-factor code, a captcha, a payment, a passkey) calls `hand_over` with that step. Its turn pauses and the chat shows a "Needs you" card with the step and three actions: Open computer, I'm done, Skip.

## Sub-features

- Open computer goes to the Computer page, which takes control on open.
- I'm done releases the person's control and answers `{"finished": true}`; the bot reads the page again and carries on. Skip answers `{"finished": false}`; the bot carries on without treating the step as done.
- "Type a message instead" (or Esc) folds the card to a bar; typing a message skips the hand-over (`SKIPPED`).
- Telegram and Discord get the usual link to the `/answer/<chat>/<call>` page, which shows the same card.
- The timeline keeps one line: "Needs you: <step> → done", "→ skipped" or "→ cancelled".

## How to get to it (user POV)

Ask a bot to sign in somewhere on the computer, for example "Open https://www.lazada.com.my and sign me in; you'll need me for the password, so hand that step over to me." Approve its browser calls.

## Driving it with Playwright MCP

Send the message as in [chat.md](chat.md), approve `computer__browser_navigate` and `computer__browser_act` with "Allow for this conversation", then poll `curl -s localhost:<backend>/api/conversations/<id>` until a `tool/call` named `hand_over` appears and the turn ends `pending`. Click Skip or I'm done on the card and read the model's next message from the stored conversation.

## Gotchas

The bot decides when to hand over; a small local model may never call the tool. After Skip it may hand over again when it still cannot go on: the description allows that.
