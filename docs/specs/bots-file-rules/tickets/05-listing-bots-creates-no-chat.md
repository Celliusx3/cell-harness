# 05. Listing bots creates no chat

**Status.** done

## What to build

`BotService.open_active_bots` stops creating the built-in bots' chats. Its body becomes the list alone.
Tests that relied on the list call to create a chat send a message first, or create the chat themselves.
Run the app with the `drive-cell-harness` skill on a new data folder, and record Assistant's empty chat answering "hi".

## Checks

A new test: on a new data folder, `GET /api/bots` returns both built-in bots, and no chat is saved for either. `make test` is green. The browser run shows the empty chat, then the answer.

## Blocked by

04
