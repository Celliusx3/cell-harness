# 01. The group service is built without a turn order

**Status.** done

## What to build

`GroupService` in `harness/bots/service/group_service.py` takes `(bots, sessions)` and uses `MENTION_TURN_ORDER` from `harness/bots/domain/turn_order.py` directly.
Delete the `TurnOrder` protocol from `turn_order.py` and its export from `harness/bots/__init__.py`. `harness/web/server.py` builds the service with two arguments.
In the tests, the 31 `GroupService(...)` constructions in 26 files go through one helper beside `no_bots` in `tests/unit/helpers.py`.
No behaviour changes.

## Checks

`make lint` and `make test` are green before and after. `grep -rnw TurnOrder harness tests` finds nothing. `grep -rn "GroupService(" tests` finds only the helper.

## Blocked by

none
