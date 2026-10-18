# 06 · Each native tool keeps its shapes in its models file

**Status.** open

**What to build.** In `backend/harness/tools/native/`, what each tool is called with and answers moves, unchanged with its name and docstring, into the tool folder's `models.py`:
- `clock/models.py`: `ClockArgs`.
- `code/models.py`: `DetailsArgs`, `ExecuteArgs`, and the list tool's `NoArgs`, now at module level.
- `subagent/models.py`: `SubagentTask`, `SubagentArgs`, `SubagentAnswered`, `SubagentStopped`, `SubagentOutcome`, `MAX_SUBAGENTS`. `SubagentRunner` stays in `tool.py`.
- `skills/models.py`: `SaveArgs`, `DeleteArgs`, `WriteFileArgs`.
- `bots/models.py`: `MessageBotArgs`. `BotMessageSender` stays in `message.py`.
- `location/models.py`: `NoArgs`, from `tool.py`.

Each door exports the same names. Tests that import a moved name by path follow.

**Checks.** `make lint` and `make test` green (1486 passed). Every native tool's name, description and input schema, saved to a scratch file before the move, are identical after it. Break: raise `MAX_SUBAGENTS` to 5; the subagent test that sends five tasks fails.

**Blocked by.** 03
