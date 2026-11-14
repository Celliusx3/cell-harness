# Groups have their own storage

Issue #149.

## Problem

Groups are saved inside the bots file, beside the bots. One repository reads and writes both lists. So the group service cannot save or list a group on its own. It asks the bot service, which only passes the group on, and the groups route asks the bot service for the groups.

Fixing that today would hand the group service five things when it is built, and the project allows four.

## What changes for you

Groups made before this change are not carried over. Their chats stay on disk, but the groups no longer show.

1. You start the app after the update. The sidebar lists your bots, and no group made before.
2. You press **New**, then **Group**, pick two bots and name the group. It appears in the sidebar, as it does today.
3. You open the group and send a message. Its members answer in turn, as they do today.

After the change the code reads this way. Groups live in their own file, with their own repository. The group service reads and saves groups through it, and tells the browser itself. The bot service, the bot repository and the bots file hold nothing about groups. The groups route asks the group service.

## Decisions

- Groups move to their own file, set by a new `groups.path` setting. It defaults to `groups.json` beside `bots.json`, in the dev config and in the Mac app's config.
- Groups saved in the bots file before this change are ignored, as the person chose. There is no move to the new file. The old list is dropped from the bots file the next time a bot is saved.
- The group service is no longer handed the turn order when it is built. It uses the one turn order directly, which frees the fourth place for the group repository. To decide at approval.
- The `TurnOrder` interface goes with that, since nothing is typed by it any more. Issue #90 adds a lead for each group, which is a choice read from the group, not from how the service is built. To decide at approval.
- A change to the groups still tells the browser with the `bots/changed` event. The sidebar already reloads bots and groups on it.
- Tests build the group service through one helper, so its 31 construction sites stop repeating its arguments.

## Out of scope

- Renaming, changing, archiving or deleting a group. That is #91, and it builds on this storage.
- A group lead. That is #90.
- A "chat not found" error for a chat that is neither a bot's nor a group's.

## How we will know it works

- The 81 tests of groups, turn order, the bot repository and the bots service pass before and after. Measured on 2026-11-14.
- New tests give the group repository a file in a temporary folder and check what it stores.
- A test reads a bots file that still holds an old list of groups. Its bots load, and no group is listed.
- In the browser on a new data folder, a new group appears in the sidebar and the groups file holds it.
- In the browser, the new group's members answer a message in turn.
