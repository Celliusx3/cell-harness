# 18. Layer channels: domain, repository and router

**Status.** done

## What to build

Move the data, the storage and the link-code route of `channels`. `telegram/`, `discord/` and `web/` keep their shape.
- `channels/protocol.py` to `channels/domain/protocol.py`
- `channels/text.py` to `channels/domain/text.py`
- `channels/repository.py` to `channels/repository/chat_repository.py`
- `channels/repositories/jsonl.py` to `channels/repository/jsonl_chat_repository.py`
- `channels/link_codes_router.py` to `channels/router/link_code_router.py`
- `channels/link_codes_schemas.py` to `channels/router/link_code_schemas.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

01
