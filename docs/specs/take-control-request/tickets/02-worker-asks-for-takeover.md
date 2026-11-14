# 02. The worker's prompt says when to ask for the screen

**Status.** open

## What to build

The worker's prompt in `harness/tickets/domain/prompts.py` says what to do when a page needs a step only the person should do. Those steps are a password, a two-factor code, a captcha, a human check, a payment or a passkey. The worker reports blocked with one question and the ask `takeover`, and never asks for those values in chat.
Record the wording in `docs/prompt-failures.md`, with the #119 run as its failure.

## Checks

A unit test: the worker prompt names the takeover ask and the human check. It fails before the wording changes.

## Blocked by

01
