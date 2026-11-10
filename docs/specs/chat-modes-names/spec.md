# Chat modes names: one word for the mode, and no duplicate code

## Problem

The chat modes code from #54 calls one thing by two words, `mode` and `approval_mode`. Several names need their docstring to be read, such as `mode_of`, `_mode_in`, `_switched` and `mode_is`. Two pieces of code are written twice, and the `/mode` word is checked in two places instead of being parsed once.

## What changes for you

Nothing a person sees changes. The code reads differently:

1. A broad object names the mode in full: `runs.set_approval_mode(id, "auto")`, `session.approval_mode(default)`, `runtime.approval_mode(session)`.
2. `Runtime` answers the mode and the last switch. No caller reaches through the toolset for the default.
3. `/mode` is parsed once into `ModeQuestion() | ModeChoice(mode) | UnknownModeWord(word)`.
4. The web routes read a chat's session through one helper.
5. The frontend's API call is `setConversationMode`, beside `stopRun` and `setBotSecrets`.

## Out of scope

- Any change in behaviour, wording a person reads, or the event format in the log.
- Names the project fixes by convention: `ApprovalModeChanged`, `SetMode`, `ModePicker`, `onModeSwitch`.

## How we will know it works

- The 49 tests in the seven mode test files pass before and after. `make lint` and `make test` stay green, at 1790 tests.
- Each moved piece is broken on purpose once, and a test fails.
- The frontend type check is clean.
