# 04 Auto picks who answers, and the reply says so

**Status.** done

**What to build.** `reply` gains `auto`, and `Group` gains
`auto_model: SecretName | None`, required with `auto`. For a message
with no @name, one call to that model returns a member's name or
`everyone`, with a confidence from 0 to 1. At 0.6 or more the pick
answers, otherwise the lead does, and any failure falls back the same
way. A `group/auto_pick` session event records the pick, and the reply
shows "Picked by Auto · 94%" under it.

**Checks.** A test with a fake model shows a sure pick answering, an
unsure one going to the lead, and an error going to the lead. In the
browser, Market Desk on Auto answers "what is NVDA's price?" with
Market Watcher, and the label shows.

**Blocked by.** 02
