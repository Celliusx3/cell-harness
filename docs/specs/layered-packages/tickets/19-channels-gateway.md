# 19. Layer channels: the gateway

**Status.** done

## What to build

Move the gateway of `channels` and the modules it imports.
- `channels/gateway.py` to `channels/service/gateway.py`
- `channels/chat_tasks.py` to `channels/service/chat_tasks.py`
- `channels/chats.py` to `channels/service/chats.py`
- `channels/following.py` to `channels/service/following.py`
- `channels/replies.py` to `channels/service/replies.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

18
