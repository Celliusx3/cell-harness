# 05 /goal runs the lead and its members in turn until the lead ends it

**Status.** done

**What to build.** In a group, a message starting `/goal ` starts a
goal run, checked before skill expansion. A new goal-run module, not
the full run service, alternates the lead and the member it names, up
to 13 turns, the lead last. The lead's and each member's goal
instructions are session events, per "Model-visible means logged".

The lead ends each turn with a `<goal>` JSON block, of status continue
(with next and task) or done, needs-you or blocked (with detail). A
missing or broken block ends the run as blocked. The chat never shows
the block.

**Checks.** An integration test with scripted model replies runs lead,
member, lead, done, and logs a `goal/end` event with status done and 3
turns. Another ends as blocked on a reply with no block, and another at
the limit. The rendered message hides the block.

**Blocked by.** 01
