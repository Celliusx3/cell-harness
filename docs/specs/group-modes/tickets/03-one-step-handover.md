# 03 A bot's @mention brings another bot in once

**Status.** done

**What to build.** In `SpeakerQueue`, a bot's reply adds the members it
names only when that bot was queued by the person's message. A bot
added by another bot's mention adds nobody. `MAX_TURNS_FROM_MENTIONS`
goes, because the queue can no longer grow past one step.

**Checks.** A unit test replays a log where Bull names Bear and Bear
names Bull. Bear speaks, and Bull does not speak again. The existing
speaker-queue tests still pass, or change where they asserted the chain
of six.

**Blocked by.** 02
