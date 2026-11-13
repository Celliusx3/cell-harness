# 20. Layer channels: around the gateway

**Status.** done

## What to build

Move the rest of the code that acts in `channels`.
- `channels/client.py` to `channels/service/client.py`
- `channels/commands.py` to `channels/service/commands.py`
- `channels/inbox.py` to `channels/service/inbox.py`
- `channels/links.py` to `channels/service/links.py`
- `channels/platforms.py` to `channels/service/platforms.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

19
