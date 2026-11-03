# 05 — the relay is its own package

## Status

done

## What to build

1. Create `harness/relay/` from `harness/mcp/relay.py`, with no change to any body.
2. Put `Upstream`, `OpenRelay`, `RelayEntry`, `Target` and `with_query` in `relay/models.py`.
3. Put `Relays` in `relay/service.py`, renamed to `RelayService`, with `RELAY_TTL_SECONDS` and `RELAY_ID_BYTES`.
4. Put `RELAY_META`, `RELAY_PREFIX`, `LOOPBACK_HOSTS`, `loopback_target` and `with_relay_url` in `relay/entry.py`.
5. Make `relay/__init__.py` export, with `__all__`, the names used outside the package.
6. Those names are `RelayService`, `Upstream`, `RELAY_PREFIX`, `RELAY_TTL_SECONDS` and `with_relay_url`.
7. Import them from `harness.relay` in `web/server.py`, `web/routes/mcp.py` and `web/routes/relay.py`.
8. Do the same in `test_relay_routes.py`, and rename `test_mcp_relay.py` to `test_relay.py`.
9. Delete `harness/mcp/relay.py`. The logger keeps its name, `harness.relay`.

## Checks

1. `make test` passes 1669 tests. `make lint` is green.
2. The 9 relay tests, 11 relay route tests and 16 app route tests pass with the same names.
3. `git grep -n "harness.mcp.relay\|\bRelays\b" backend` finds nothing.

## Blocked by

none
