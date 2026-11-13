# 12. Layer runs

**Status.** open

## What to build

Move the five modules of `runs`. Each one acts on a turn in flight, so `runs` has only a service folder.
- `runs/service.py` to `runs/service/run_service.py`
- `runs/run.py` to `runs/service/run.py`
- `runs/chain.py` to `runs/service/chain.py`
- `runs/subscribe.py` to `runs/service/subscribe.py`
- `runs/bot_messages.py` to `runs/service/bot_messages.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

01
