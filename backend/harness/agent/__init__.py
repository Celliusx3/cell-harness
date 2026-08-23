"""The agent and the loop that drives it — phase 1.

An agent is a model with a job. The loop executes one turn: assemble a request,
stream the response, dispatch the tools it asked for, repeat until nothing is
owed. A **step** is one model request plus its tools; a **turn** is zero or more
steps.

The rule that keeps later phases cheap: the loop derives its history from
`session.derive_messages(log)` on every step — never from a list it accumulated.
Resume, fork, and compaction are all free consequences of that; an accumulated
list makes each of them a rewrite of this package.

The system prompt is deliberately not part of the log. It is prepended per
request, so it can reflect the agent running *this* turn.
"""
