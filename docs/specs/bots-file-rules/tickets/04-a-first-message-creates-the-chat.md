# 04. A first message creates the chat

**Status.** open

## What to build

`RunService.hear_when_free` in `harness/runs/service/run_service.py` creates the chat when its bot or group exists and no chat is saved under that id.
A chat whose bot is gone still raises, so `scheduler.py` and `bot_messages.py` keep ending and dropping as they do.
The web channel's conversation route shows an empty chat for a built-in bot with no saved chat.

## Checks

Each test uses a new data folder and never lists the bots. A schedule due in Assistant's chat runs a turn and stays active. A `message_bot` call to Bot builder is delivered and answered. `GET` of Assistant's conversation returns an empty chat, not a 404. A schedule for a deleted bot still ends.

## Blocked by

none
