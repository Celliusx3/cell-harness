# 02 Every node is told its workspace, and uploads land there

**Status.** done

**What to build.**

- An upload is written into a fresh subfolder of the chat's workspace instead of `<files root>/<chat id>/`.
- A file is served when it is in the chat's workspace or its old folder, so old uploads still open.
- Each node is told its workspace in one line in `prompts.py`.
- In a group, the line also names the bot's own workspace and says it may work there.
- The line follows "Model-visible means logged".
- It is either text rebuilt every step, like the skill list, or a logged session event.
- The worker's files-folder line names its workspace too.

**Checks.**

- An integration test uploads to a bot's chat. The file lands under `workspaces/<bot id>/`, and its download works.
- An upload stored under the old folder still downloads.
- A turn in a group gets the line naming the group's workspace and the bot's own.
- A turn in a bot's chat gets the line naming only the bot's.
- `make test` passes at 80%.

**Blocked by.** 01
