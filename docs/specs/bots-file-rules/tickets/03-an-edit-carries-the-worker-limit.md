# 03. An edit carries the worker limit

**Status.** done

## What to build

Make `max_workers` a required field of `BotEdit` in `harness/bots/domain/models.py`, and drop the "kept" branch in `BotService.update`.
In the frontend, `BotEdit` in `lib/types.ts` loses the `?`, and `components/setup/SetupForm.tsx` sends `assistant.max_workers`.
Update the `BotEdit(...)` calls in `tests/bot_models.py` and three unit test files.

## Checks

In `tests/integration/test_web_bot_worker_limit.py`, a `PUT /api/bots/{id}` without `max_workers` returns 422, and one with 2 saves 2. A frontend test of the setup form shows the edit it sends holds the worker limit.

## Blocked by

none
