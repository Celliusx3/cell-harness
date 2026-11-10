# 02 · The bot is told the mode, and when you change it

**Status.** open

**What to build.** `RunService.set_mode` also appends an `ApplicationMessageEvent` when the mode really changes: "The approval mode changed from ask to auto (changed by the user)." A switch to the mode already on appends nothing.

Each step's request ends with one system-reminder line that names the current mode. It comes after the whole history, so the start of the request stays the same across a switch. The line is rebuilt from the log on every step and is not logged. The two sentences live in `prompts.py`:

- ask: "Approval mode: ask. A call that changes something may wait for the user's approval."
- auto: "Approval mode: auto. Your calls run without asking the user."

Files: `prompts.py`, `runtime/service.py`, `runs/service.py`.

**Checks.** A unit test on the request: its last message carries the mode line, and a switch leaves every earlier message the same. An integration test: a switch to auto mid-turn puts the notice in front of the model on its next step. A switch to the mode already on adds no notice. `make lint` and `make test` stay green.

**Blocked by.** 01
