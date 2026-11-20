# 07 A card shows how a goal run ended, and Stop ends it

**Status.** done

**What to build.** The `goal/end` event shows as a card in the chat.
The card has the goal, the lead, the turns used out of 13, the status
and the detail. Stop during a goal run logs a `goal/end` with status stopped
before it cancels the run.

**Checks.** A frontend test renders the card for each status. An
integration test stops a running goal and finds the stopped event. In
the browser, Stop during a goal run shows the card with stopped.

**Blocked by.** 05
