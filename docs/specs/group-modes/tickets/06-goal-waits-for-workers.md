# 06 A goal run waits for a member's workers, and stops on a loop

**Status.** open

**What to build.** A member's turn in a goal run ends only when that
bot's tickets from this chat are finished and their reports are heard.
Past a 10-minute limit, the lead's next turn carries a note that the
member is still busy. The third such wait ends the run as blocked, and
so does the same task given to the same member three times.

**Checks.** An integration test routes a ticket in a member's turn, and
the lead speaks only after the report. A test with a ticket that never
finishes shows the note, then blocked after three. A test that repeats
a task shows blocked.

**Blocked by.** 05
