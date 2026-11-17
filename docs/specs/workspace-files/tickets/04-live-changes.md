# 04 The panel shows changes at once

**Status.** done

**What to build.**

- A route `GET /api/workspaces/{chat_id}/changes` streams server-sent events while the panel is open. Each event names the folder that changed, relative to the workspace.
- The harness watches the workspace with `watchfiles` (added as a direct dependency). The watch stops when the browser disconnects, per "A watcher owns nothing".
- The panel lists the open folder again when an event names it.

**Checks.**

- An integration test opens the stream, writes a file into the workspace, and gets an event naming its folder within two seconds.
- Closing the stream stops the watch.
- In the real app, a file a worker writes appears in the open panel without a reload.
- `make lint` and `make test` pass at 80%.

**Blocked by.** 01
