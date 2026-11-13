# 02. The computer server offers request_takeover

**Status.** open

## What to build

Add `request_takeover` to the computer server, in a new `computer/tools/takeover.py`, registered in `computer/server.py`. It takes `{ reason: str }`, declares that it waits for the person, and returns its card's data.
Its description follows Rakazo's: call it for passwords, 2FA, captchas, human checks, payments or passkeys, and never ask for those values in chat.
`COMPUTER_INSTRUCTIONS` and `browser_act`'s stop rule say "call request_takeover" in place of #128's wording, and a failed browser step says so too. Record the wording in `docs/prompt-failures.md`.

## Checks

Server tests: the tool declares the wait, takes only a reason, and returns it. The instructions, the stop rule and the failed-step note each name `request_takeover`. All fail before the tool exists.

## Blocked by

01, and #128 merged first, since this ticket changes its wording
