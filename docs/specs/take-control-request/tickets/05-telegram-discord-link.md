# 05. Telegram and Discord get the reason and a link

**Status.** open

## What to build

On Telegram and Discord, a waiting MCP tool gets the same line as a client tool. The line says what it asks, with the `/answer/{id}/{call}` link from `harness/channels/service/replies.py`.
The answer page shows the tool's card, so the person can take control there.

## Checks

A test with a fake Telegram channel: a waiting `request_takeover` sends one line with the reason and the answer link. The link opens the card in a browser run.

## Blocked by

01, 03
