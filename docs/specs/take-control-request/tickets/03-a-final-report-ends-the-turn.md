# 03. A final report ends the worker's turn

**Status.** done

## What to build

A real model kept calling tools after it reported blocked: 69 steps and about 55 more takeover reports in one turn. A tool's `Ok` can now say it ends the turn (`ends_turn`), and `ticket_report` says so for every state but progress.
The turn loop closes the turn after that step, as it does for a pending call, and names no tool. The tool-call block moves to `harness/runtime/step_tools.py`, and the step opening to `harness/runtime/step_open.py`, to keep `turn.py` under its caps.

## Checks

A loop test: a tool that ends the turn is called once, and the model's next call never runs. A `ticket_report` test: blocked and ready end the turn, and progress does not. Both fail before the change.

## Blocked by

01
