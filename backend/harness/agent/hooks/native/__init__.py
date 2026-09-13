"""Hooks implemented in this process, one folder each.

The four here are the loop guardrail — hooks that notice the model repeating
itself. Each answers two questions about one call against the turn so far:
*should this run?* and, once it has, *is there something to tell the model?*
Over the tool calls of the **current turn**:

| Hook | Counts | warns | refuses |
|---|---|---|---|
| `exact_failure` | same tool + arguments failing, since that pair last succeeded | 2 | 5 |
| `same_tool_failure` | same tool failing with any arguments, since it last succeeded | 3 | 8 |
| `no_progress` | same tool + arguments returning the identical result | 2 | 5 |
| `repeated_call` | same tool + arguments called consecutively, results aside | 3, 5, 8 | never |

A warning is a line the model reads beside the step's results (the loop logs
it as an `application/message`); a refusal is pre-execution — the
call is answered with `error: …` and the tool never runs. The composition root
puts them in one `HookChain`, which asks them one by one in that order and
takes the first answer — so the order is precedence, specific before general —
and runs each under the hook timeout, failing open, so one hook's bug cannot
silence the others. A fifth is a new folder and one more entry in that tuple;
nothing here or in the loop changes.

**It is a fold, not a counter.** Every decision is computed from the session
log — `tool/call` paired with its `tool/result`, like `Session.tools_selected()`
folds `tool_reference` blocks — so there is nothing to keep, nothing to restore
on resume, and nothing a blocked call has to avoid mutating. Its own refusals
are logged like any result and skipped when counting, so refusing never
inflates the count that caused it. `hooks/turn.py` is that fold; a hook here
sees only its result.

What this does not see: calls a *script* makes. A program that hammers a failing
tool a hundred times inside one `execute_typescript` is one call here, bounded
by the script's own timeout. The dispatcher is the one door scripts pass through
and the log is what this reads, so the guardrail is a hook at the loop.

Every message in here is prompt text, and prompt text is code: the wording that
fixes an observed failure carries that failure in a comment beside it.
"""
