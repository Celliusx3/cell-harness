# 01 — A chat app hears a turn it did not start

**Status.** done

**What to build.** Closes #85. When a run starts in a conversation that no chat
app's message started (today `RunService.hear`, from `runs/bot_messages.py`),
every chat linked to that conversation follows it to its end, as it follows a
turn it started. Touches `channels/gateway.py`, `channels/following.py`, the
place `hear` is called from, and `ChatState` lookups via `ChatRepository.chats_of`.
A chat that started the turn is not followed twice.

**Checks.** An integration test with a fake Telegram channel linked to
Assistant: Assistant messages another bot, that bot answers, Assistant's woken
turn's reply is pushed to the fake channel once. Fails today.

**Blocked by.** none
