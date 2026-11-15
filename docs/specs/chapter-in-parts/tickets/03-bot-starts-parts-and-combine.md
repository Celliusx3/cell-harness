# 03 The bot starts the parts, then the combine

**Status.** done

**What to build.** In cell-harness, `ORCHESTRATOR_INTRO` in `backend/harness/tickets/domain/prompts.py` gains three rules:

- When a worker's ready report lists parts, accept one ticket per part with the task lines as given.
- Start the combine ticket only after every part reports ready.
- When a combine reports pages missing, retry the parts that own them.

A worker's first message also says how many workers its bot runs at once, `Bot.max_workers`, read as its first turn starts. The prepare worker makes that many parts. Each new text gets its row in `docs/prompt-failures.md`.

**Checks.** An integration test checks that a worker's first message says "Your bot can run 3 workers at once." `make lint` and `make test` pass. Whether the bot waits for every part before the combine is the model's judgement, so a scripted test would only test its script. Ticket 04's real run checks it.

**Blocked by.** 02
