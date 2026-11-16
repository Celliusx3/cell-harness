# 05 Deleting a bot deletes its workspace, and the last member's deletion deletes the group's

**Status.** open

**What to build.** `BotLifecycleService.delete` deletes the bot's workspace folder after it deletes the bot. Then, for each group that lists the bot, it deletes the group's workspace when none of the group's `member_ids` is a stored bot any more. An archived bot is still stored, so it keeps both. The deletion is a files repository method. The group check is a plain function over the group and the stored bots' ids.

**Checks.**

- A unit test of the check: a group with one deleted and one archived member keeps its workspace.
- A group whose members are all deleted has it deleted.
- An integration test deletes one member of a two-member group.
- Its workspace is gone, and the group's workspace stays.
- Deleting the second member deletes the group's workspace.
- Archiving a bot keeps its workspace.
- `make test` passes at 80%.

**Blocked by.** 01
