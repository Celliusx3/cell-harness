"""The append-only session log — phase 1.

The single source of truth for an agent's interaction history. Model message
history is *derived* from this log (`derive_messages`), never stored beside it;
replay is re-derivation from the same events.

The invariant this subpackage exists to uphold: **model-visible means logged.**
Anything that reaches a model request must be reconstructable from the log. A new
model-visible input therefore requires a new event type, never a side channel.
`invariant.assert_derivable` enforces it from phase 3, when resume makes it
testable — but the loop must be written against the log from phase 1, because
retrofitting that is a rewrite of `agent/`.

Everything downstream follows from it: fork is a log prefix, resume is replay,
compaction is an appended event pair, telemetry is a projection.
"""
