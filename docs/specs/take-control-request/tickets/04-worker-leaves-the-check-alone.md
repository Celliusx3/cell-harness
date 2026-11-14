# 04. The worker leaves the check alone

**Status.** done

## What to build

A real model asked the person to do the check, and kept working on it at the same time. It clicked "I'm not a robot", opened the image challenge, then pressed Play and Verify.
The worker's prompt in `harness/tickets/domain/prompts.py` says not to click, answer or solve the check itself. Record the wording in `docs/prompt-failures.md` with that run.

## Checks

A unit test: the worker prompt says not to click or solve the check. It fails before the wording changes. The real-model eval runs again and counts the clicks on the check.

## Blocked by

02, 03
