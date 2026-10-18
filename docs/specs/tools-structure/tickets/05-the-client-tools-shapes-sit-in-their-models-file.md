# 05 · The client tools' shapes sit in their models file

**Status.** open

**What to build.** `backend/harness/tools/client/models.py` holds, moved unchanged with their docstrings: `DECLINED`, `UNAVAILABLE`, `Shared`, `Declined`, `Unavailable`, `ClientOutput`, `ClientTool` from `catalog.py`; `PendingCall` from `pending.py`; `Refused`, `Accepted` from `service.py`. `catalog.py` keeps `ClientTools` and its helpers, `pending.py` keeps `pending_calls` and `still_pending`, and `service.py` keeps `ClientToolService`. The client door exports the same names, from their new file. Tests that import a moved name from `catalog`, `pending` or `service` by path follow.

**Checks.** `make lint` and `make test` green (1486 passed). `git grep -nE "from harness\.tools\.client\.(catalog|pending|service) import .*(PendingCall|Accepted|Refused|Shared|Declined|Unavailable|ClientTool\b)" -- backend` finds nothing. Break: drop `min_length=1` from `Unavailable.reason`; the client tools tests fail.

**Blocked by.** 04
