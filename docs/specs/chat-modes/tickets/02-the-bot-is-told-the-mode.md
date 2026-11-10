# 02 · The bot is told the mode, and when you change it

**Status.** done

**What to build.** At the start of each step, the runtime compares the chat's mode now with its mode at the previous step. When they differ, it appends an `ApplicationMessageEvent` for this turn: "The approval mode changed from ask to auto (changed by the user)." The note waits for the step start because a message between a tool call and its result breaks the request.

A chat with no step yet gets no note. A switch away and back between two steps gets no note either.

Once a chat has a switch in its history, each request ends with one system-reminder message that names the current mode. It comes after the whole history, so the start of the request stays the same across a switch. It is rebuilt from the log on every step and is not logged. A chat never switched gets no line, because it behaves as it always did.

The sentences live in `prompts.py`:

- ask: "Approval mode: ask. A call that changes something may wait for the user's approval."
- auto: "Approval mode: auto. Your calls run without asking the user."
- changed: "The approval mode changed from {before} to {after} (changed by the user)."

Files: `prompts.py`, `runtime/service.py`, `runtime/turn.py`, and a small pure module for the comparison if it keeps those files short.

**Checks.** `backend/tests/unit/test_chat_mode_told.py`: a chat never switched has no mode line. A switched chat ends each request with the line, and every earlier message stays the same. A switch since the last step is told once, at the next step. A switch away and back tells nothing.

A switch before the first step tells nothing but the line. `make lint` and `make test` stay green.

**Blocked by.** 01
