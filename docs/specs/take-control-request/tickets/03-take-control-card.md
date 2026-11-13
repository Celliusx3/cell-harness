# 03. The card shows the reason, Take control and Hand back

**Status.** open

## What to build

Give `request_takeover` its card: an HTML resource in the computer server, beside `preview.html`.
It shows the bot's reason and **Take control**. Pressing it takes control and opens the docked computer (`frontend/components/computer/ComputerDock.tsx`). Read first how #109 docks it.
**Hand back** releases the screen and posts the call's answer, so the bot's next turn starts. A skipped request shows as skipped.

## Checks

A browser run in a private copy: a bot calls `request_takeover`. The card shows the reason. **Take control** docks the computer, and **Hand back** starts the bot's next turn, which reads the page.

## Blocked by

01, 02
