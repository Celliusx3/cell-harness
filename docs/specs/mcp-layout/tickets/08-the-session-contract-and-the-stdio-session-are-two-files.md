# 08 — the session contract and the stdio session are two files

## Status

done

## What to build

1. In `harness/mcp/client.py`, rename `ClientLike` to `McpClient` and `ClientFactory` to `McpClientFactory`.
2. That file keeps only the contract, as `llm/client.py` does.
3. Move `open_client` to a new `harness/mcp/clients/stdio.py`, renamed to `open_stdio_client`.
4. Keep its note on how the SDK merges `env`. It is a note on an outside library.
5. Give `harness/mcp/clients/__init__.py` a one-line docstring, as `secrets/repositories/__init__.py` has.
6. Update `connection.py`, `service.py`, `mcp/__init__.py` and `tests/webapp.py`.

## Checks

1. `make test` passes 1669 tests. `make lint` is green.
2. The 5 stdio tests in `test_mcp_stdio.py` connect a real server through the moved session.
3. `git grep -nwE "ClientLike|ClientFactory|open_client" backend` finds nothing.

## Blocked by

07
